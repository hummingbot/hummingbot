"""
System R Risk-Managed Pure Market Making Strategy

A pure market making script that gates every order through System R's
pre-trade risk intelligence API before execution. Orders that fail the
risk gate are suppressed, protecting the bot from placing trades that
violate portfolio risk limits, drawdown constraints, or adverse market
regime conditions.

System R API docs & demo agent:
  https://github.com/System-R-AI/demo-trading-agent

Setup:
  1. Get a free API key at https://agents.systemr.ai
  2. Set the SYSTEMR_API_KEY environment variable, or pass it in the config.
  3. Configure exchange, trading pair, spreads, and risk parameters below.

Usage:
  In the Hummingbot client, run:
    >>> create --script-config systemr_risk_managed_pmm

Risk gate payload (POST https://agents.systemr.ai/v1/compound/pre-trade-gate):
  {
    "symbol": "ETH-USDT",
    "direction": "long",
    "entry_price": 3500.00,
    "stop_price": 3465.00,
    "equity": 10000.00
  }

The gate returns {"allow": true/false, "reasons": [...]}. Only orders with
allow=true are placed. Rejected orders are logged with reasons.
"""
import asyncio
import logging
import os
from decimal import Decimal
from typing import Dict, List, Optional

import aiohttp
from pydantic import Field

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import MarketDict, OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase

SYSTEMR_PRE_TRADE_GATE_URL = "https://agents.systemr.ai/v1/compound/pre-trade-gate"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class SystemRRiskManagedPMMConfig(StrategyV2ConfigBase):
    script_file_name: str = os.path.basename(__file__)
    controllers_config: List[str] = []

    # Exchange & pair
    exchange: str = Field(default="binance_paper_trade", description="The exchange connector to use.")
    trading_pair: str = Field(default="ETH-USDT", description="The trading pair to market-make on.")

    # PMM parameters
    order_amount: Decimal = Field(default=Decimal("0.01"), description="Order size in base asset.")
    bid_spread: Decimal = Field(default=Decimal("0.001"), description="Spread below mid price for buy orders.")
    ask_spread: Decimal = Field(default=Decimal("0.001"), description="Spread above mid price for sell orders.")
    order_refresh_time: int = Field(default=15, description="Seconds between order refreshes.")

    # Risk parameters sent to System R
    equity: Decimal = Field(default=Decimal("10000"), description="Account equity for position-sizing checks.")
    stop_loss_pct: Decimal = Field(
        default=Decimal("0.01"),
        description="Stop-loss distance as fraction of entry price (e.g. 0.01 = 1%).",
    )

    # System R API key (falls back to SYSTEMR_API_KEY env var)
    systemr_api_key: str = Field(
        default="",
        description="System R API key. Leave blank to use the SYSTEMR_API_KEY env var.",
    )

    def update_markets(self, markets: MarketDict) -> MarketDict:
        markets[self.exchange] = markets.get(self.exchange, set()) | {self.trading_pair}
        return markets


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------

class SystemRRiskManagedPMM(StrategyV2Base):
    """
    Pure market making strategy with System R pre-trade risk gating.

    On every tick cycle the bot:
      1. Computes bid/ask prices from the mid price.
      2. Calls the System R pre-trade gate for each proposed order.
      3. Places only those orders that the risk gate approves.
      4. Logs rejected orders with the reasons returned by the API.
    """

    create_timestamp = 0
    _http_session: Optional[aiohttp.ClientSession] = None

    # Counters for format_status display
    _orders_approved: int = 0
    _orders_rejected: int = 0

    def __init__(self, connectors: Dict[str, ConnectorBase], config: SystemRRiskManagedPMMConfig):
        super().__init__(connectors, config)
        self.config = config

    # -- HTTP session lifecycle --------------------------------------------

    def _get_api_key(self) -> str:
        """Resolve the API key from config or environment."""
        return self.config.systemr_api_key or os.environ.get("SYSTEMR_API_KEY", "")

    def _ensure_session(self) -> aiohttp.ClientSession:
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()
        return self._http_session

    async def on_stop(self):
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()

    # -- Risk gate ---------------------------------------------------------

    async def _check_risk_gate(self, direction: str, entry_price: Decimal, stop_price: Decimal) -> dict:
        """
        Call System R pre-trade gate.

        Returns a dict with at least:
          {"allow": bool, "reasons": list[str]}

        On network errors the gate defaults to REJECT (fail-closed).
        """
        session = self._ensure_session()
        api_key = self._get_api_key()

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "symbol": self.config.trading_pair,
            "direction": direction,
            "entry_price": float(entry_price),
            "stop_price": float(stop_price),
            "equity": float(self.config.equity),
        }

        try:
            async with session.post(
                SYSTEMR_PRE_TRADE_GATE_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    body = await resp.text()
                    self.logger().warning(
                        f"System R gate returned HTTP {resp.status}: {body}"
                    )
                    return {"allow": False, "reasons": [f"HTTP {resp.status}"]}
        except Exception as e:
            # Fail-closed: if the risk service is unreachable, reject the order.
            self.logger().warning(f"System R gate unreachable ({e}); rejecting order (fail-closed).")
            return {"allow": False, "reasons": [f"Network error: {e}"]}

    # -- Order lifecycle ---------------------------------------------------

    def on_tick(self):
        if self.create_timestamp <= self.current_timestamp:
            self.cancel_all_orders()
            # Schedule the async risk-gated order flow
            asyncio.ensure_future(self._risk_gated_order_cycle())
            self.create_timestamp = self.config.order_refresh_time + self.current_timestamp

    async def _risk_gated_order_cycle(self):
        """Create proposals, gate each through System R, place approved ones."""
        proposals = self._create_proposal()
        approved: List[OrderCandidate] = []

        for order in proposals:
            direction = "long" if order.order_side == TradeType.BUY else "short"
            entry_price = order.price

            # Compute the stop price based on the configured stop-loss percentage
            if direction == "long":
                stop_price = entry_price * (1 - self.config.stop_loss_pct)
            else:
                stop_price = entry_price * (1 + self.config.stop_loss_pct)

            gate_result = await self._check_risk_gate(direction, entry_price, stop_price)

            if gate_result.get("allow"):
                approved.append(order)
                self._orders_approved += 1
                self.logger().info(
                    f"Risk gate APPROVED {direction.upper()} {self.config.trading_pair} "
                    f"@ {entry_price}"
                )
            else:
                self._orders_rejected += 1
                reasons = gate_result.get("reasons", [])
                self.logger().info(
                    f"Risk gate REJECTED {direction.upper()} {self.config.trading_pair} "
                    f"@ {entry_price} -- reasons: {reasons}"
                )

        if approved:
            adjusted = self._adjust_proposal_to_budget(approved)
            self._place_orders(adjusted)

    # -- PMM helpers (mirrors simple_pmm.py) --------------------------------

    def _create_proposal(self) -> List[OrderCandidate]:
        ref_price = self.connectors[self.config.exchange].get_price_by_type(
            self.config.trading_pair, PriceType.MidPrice
        )
        buy_price = ref_price * (1 - self.config.bid_spread)
        sell_price = ref_price * (1 + self.config.ask_spread)

        buy_order = OrderCandidate(
            trading_pair=self.config.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal(self.config.order_amount),
            price=buy_price,
        )
        sell_order = OrderCandidate(
            trading_pair=self.config.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal(self.config.order_amount),
            price=sell_price,
        )
        return [buy_order, sell_order]

    def _adjust_proposal_to_budget(self, proposal: List[OrderCandidate]) -> List[OrderCandidate]:
        return self.connectors[self.config.exchange].budget_checker.adjust_candidates(
            proposal, all_or_none=True
        )

    def _place_orders(self, proposal: List[OrderCandidate]) -> None:
        for order in proposal:
            if order.order_side == TradeType.SELL:
                self.sell(
                    connector_name=self.config.exchange,
                    trading_pair=order.trading_pair,
                    amount=order.amount,
                    order_type=order.order_type,
                    price=order.price,
                )
            elif order.order_side == TradeType.BUY:
                self.buy(
                    connector_name=self.config.exchange,
                    trading_pair=order.trading_pair,
                    amount=order.amount,
                    order_type=order.order_type,
                    price=order.price,
                )

    def cancel_all_orders(self):
        for order in self.get_active_orders(connector_name=self.config.exchange):
            self.cancel(self.config.exchange, order.trading_pair, order.client_order_id)

    # -- Event handlers ----------------------------------------------------

    def did_fill_order(self, event: OrderFilledEvent):
        msg = (
            f"{event.trade_type.name} {round(event.amount, 2)} "
            f"{event.trading_pair} {self.config.exchange} at {round(event.price, 2)}"
        )
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)

    # -- Status display ----------------------------------------------------

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = [
            "",
            "  System R Risk-Managed PMM",
            f"    Exchange       : {self.config.exchange}",
            f"    Trading pair   : {self.config.trading_pair}",
            f"    Bid spread     : {self.config.bid_spread}",
            f"    Ask spread     : {self.config.ask_spread}",
            f"    Order amount   : {self.config.order_amount}",
            f"    Stop-loss %    : {self.config.stop_loss_pct}",
            f"    Equity         : {self.config.equity}",
            "",
            "  Risk Gate Stats",
            f"    Orders approved: {self._orders_approved}",
            f"    Orders rejected: {self._orders_rejected}",
        ]
        return "\n".join(lines)
