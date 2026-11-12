"""Hummingbot 2.17 V2 paper script. A spot grid bounded by the served walls."""
from __future__ import annotations

import asyncio
from collections import deque
from decimal import Decimal
from pathlib import Path
import sys
from typing import Literal

from pydantic import Field, SecretStr
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE if (HERE / "hk_strategy_core.py").is_file() else HERE.parents[1] / "strategies"))
from hk_strategy_core import LevelsFeed, grid_quotes


class HKWallGridConfig(StrategyV2ConfigBase):
    script_file_name: str = Path(__file__).name
    exchange: Literal["binance_paper_trade"] = "binance_paper_trade"
    trading_pair: Literal["BTC-USDT"] = "BTC-USDT"
    quote_budget: Decimal = Field(default=Decimal("100"), gt=0, le=1000)
    api_key: SecretStr = Field(default_factory=lambda: SecretStr(""), repr=False)
    probe: bool = False

    def update_markets(self, markets):
        markets[self.exchange] = markets.get(self.exchange, set()) | {self.trading_pair}
        return markets


class HKWallGrid(StrategyV2Base):
    def __init__(self, connectors, config: HKWallGridConfig):
        super().__init__(connectors, config)
        self.config = config
        self._feed = LevelsFeed(key=config.api_key.get_secret_value() or None, probe=config.probe)
        self._plan = None
        self._inventory = Decimal("0")
        self._owned = deque(maxlen=4096)
        self._fills = deque(maxlen=8192)
        self._refresh_task = None
        self._next_quote = 0.0
        self._flatten_order = None
        self._closing = False
        self._plan_started_at = 0.0
        self._next_flatten_attempt = 0.0

    def _active_orders(self):
        return [order for order in self.get_active_orders(self.config.exchange)
                if order.client_order_id in self._owned]

    def _cancel_quotes(self, orders):
        for order in orders:
            self.cancel(self.config.exchange, self.config.trading_pair, order.client_order_id)

    def _remember(self, order_id):
        if order_id:
            self._owned.append(order_id)
        return order_id

    def _flatten(self, orders):
        # Cancel acknowledgements come before replacement or inventory close.
        if orders:
            self._cancel_quotes(orders)
            return
        if (self._inventory > 0 and self._flatten_order is None
                and self.current_timestamp >= self._next_flatten_attempt):
            self._next_flatten_attempt = self.current_timestamp + 60
            connector = self.connectors[self.config.exchange]
            amount = connector.quantize_order_amount(self.config.trading_pair, self._inventory)
            if amount > 0:
                self._flatten_order = self._remember(self.sell(
                    self.config.exchange, self.config.trading_pair, amount, OrderType.MARKET))
        if self._inventory <= 0:
            self._plan = None

    def on_tick(self):
        now = self.current_timestamp
        if now >= self._feed.next_poll and (self._refresh_task is None or self._refresh_task.done()):
            self._refresh_task = asyncio.create_task(asyncio.to_thread(self._feed.poll, now))
        connector = self.connectors[self.config.exchange]
        mid = float(connector.get_price_by_type(self.config.trading_pair, PriceType.MidPrice))
        sample = self._feed.timeline.at(now)
        orders = self._active_orders()
        if self._flatten_order is not None:
            return
        if self._closing:
            self._flatten(orders)
            if self._inventory <= 0 and not orders:
                self._closing = False
            return
        if sample is None:
            self._closing = True
            self._flatten(orders)
            return
        if self._plan is None or (self._inventory == 0 and not orders):
            self._plan = sample.long_plan(mid, now)
            self._plan_started_at = now
        if (self._plan is None or not self._plan.stop < mid < self._plan.target
                or now - self._plan_started_at >= 86400):
            self._closing = True
            self._flatten(orders)
            return
        if now < self._next_quote:
            return
        if orders:
            self._cancel_quotes(orders)
            return
        proposal = self.create_proposal(mid)
        adjusted = connector.budget_checker.adjust_candidates(proposal, all_or_none=True)
        for order in adjusted:
            if order.amount <= 0:
                continue
            submit = self.buy if order.order_side == TradeType.BUY else self.sell
            self._remember(submit(self.config.exchange, self.config.trading_pair,
                                  order.amount, OrderType.LIMIT, order.price))
        self._next_quote = now + 30

    def create_proposal(self, mid):
        connector = self.connectors[self.config.exchange]
        best_ask = connector.get_price(self.config.trading_pair, True)
        best_bid = connector.get_price(self.config.trading_pair, False)
        quotes = grid_quotes(self._plan, mid, float(self._inventory), quote_budget=float(self.config.quote_budget))
        proposal = []
        remaining_sell = self._inventory
        remaining_buy = max(Decimal("0"), self.config.quote_budget - self._inventory * Decimal(str(mid)))
        for side, price, amount in quotes:
            price = connector.quantize_order_price(self.config.trading_pair, Decimal(str(price)))
            amount = connector.quantize_order_amount(self.config.trading_pair, Decimal(str(amount)))
            cap = remaining_sell if side == "sell" else remaining_buy / price
            amount = connector.quantize_order_amount(self.config.trading_pair, min(amount, cap))
            if amount > cap:
                continue
            # A quote must remain passive after exchange rounding.
            if amount <= 0 or (side == "buy" and price >= best_ask) or (side == "sell" and price <= best_bid):
                continue
            proposal.append(OrderCandidate(
                trading_pair=self.config.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                order_side=TradeType.BUY if side == "buy" else TradeType.SELL,
                amount=amount, price=price))
            if side == "buy":
                remaining_buy -= amount * price
            else:
                remaining_sell -= amount
        return proposal

    def did_fill_order(self, event):
        if event.order_id not in self._owned:
            return
        identity = (event.order_id, event.exchange_trade_id or
                    (event.timestamp, str(event.amount), str(event.price)))
        if identity in self._fills:
            return
        self._fills.append(identity)
        delta = event.amount if event.trade_type == TradeType.BUY else -event.amount
        fee = event.trade_fee
        base_fee = sum((item.amount for item in fee.flat_fees if item.token == "BTC"), Decimal("0"))
        if (fee.percent_token == "BTC" or
                (fee.percent_token is None and isinstance(fee, DeductedFromReturnsTradeFee)
                 and event.trade_type == TradeType.BUY)):
            base_fee += event.amount * fee.percent
        self._inventory += delta - base_fee
        self._inventory = max(Decimal("0"), self._inventory)

    def did_complete_sell_order(self, event):
        if event.order_id == self._flatten_order:
            self._flatten_order = None

    def did_fail_order(self, event):
        if event.order_id == self._flatten_order:
            self._flatten_order = None

    def format_status(self):
        error = self._feed.last_error or "none"
        return f"Paper spot grid. Example inventory {self._inventory} BTC. Levels error: {error}."

    async def on_stop(self):
        if self._refresh_task is not None:
            self._refresh_task.cancel()
        self._cancel_quotes(self._active_orders())
        await super().on_stop()
