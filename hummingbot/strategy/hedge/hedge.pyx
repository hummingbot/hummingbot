#!/usr/bin/env python
from collections import (
    defaultdict,
    deque
)
from decimal import Decimal
import logging
from math import (
    floor,
    ceil
)
from numpy import isnan
import pandas as pd
from typing import (
    List,
    Tuple,
    Optional,
    Dict,
    Set
)

from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.clock cimport Clock
from hummingbot.core.event.events import TradeType
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.event.events import OrderType
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.strategy.strategy_base cimport StrategyBase
from hummingbot.strategy.strategy_base import StrategyBase
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.core.event.events import (PositionSide, PositionMode)
from hummingbot.strategy.hedge.exchange_pair import ExchangePairTuple
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils import convert_from_exchange_trading_pair, convert_to_exchange_trading_pair

NaN = float("nan")
s_decimal_zero = Decimal(0)
s_decimal_nan = Decimal("nan")
s_logger = None

cdef class HedgeStrategy(StrategyBase):
    @classmethod
    def logger(cls):
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def init_params(self,
                    exchanges: ExchangePairTuple,
                    market_infos: Dict[str, MarketTradingPairTuple],
                    hedge_ratio: Decimal,
                    status_report_interval: float = 900,
                    minimum_trade: Decimal = 11,
                    leverage: int = 5,
                    position_mode: str = "ONEWAY",
                    hedge_interval: float = 0.1,
                    slippage: Decimal = 0.05,
                    ):

        self._exchanges = exchanges
        self._market_infos = market_infos
        self._hedge_ratio = hedge_ratio
        self._minimum_trade = minimum_trade
        self._all_markets_ready = False
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self._wallet_df = pd.DataFrame()
        self._position_mode = PositionMode.HEDGE if position_mode == "Hedge" else PositionMode.ONEWAY
        self._leverage = leverage
        self.c_add_markets([exchanges.maker, exchanges.taker])
        self._last_trade_time = {}
        self._shadow_taker_balance = {}
        self._update_shadow_balance_interval = 600
        self._hedge_interval = hedge_interval
        self._slippage = slippage

    @property
    def order_ids(self) -> Dict[MarketTradingPairTuple, List[LimitOrder]]:
        return self._sb_order_tracker.market_pair_to_active_orders

    def get_shadow_position(self, trading_pair: str):
        return self._shadow_taker_balance[trading_pair]

    def set_shadow_position(self, trading_pair: str, value):
        self._shadow_taker_balance[trading_pair] = value

    def update_shadow_position(self, trading_pair: str, value):
        self._shadow_taker_balance[trading_pair] = self._shadow_taker_balance[trading_pair] + value

    @property
    def active_positions(self) -> List[LimitOrder]:
        return self._exchanges.taker.account_positions

    def get_position_amount(self, trading_pair: str):
        for idx in self.active_positions.values():
            if idx.trading_pair == trading_pair:
                return idx.amount
        return self.get_shadow_position(trading_pair)

    def get_balance(self, maker_asset: str):
        return self._exchanges.maker.get_balance(maker_asset)

    cdef object check_and_hedge_asset(self,
                                      str maker_asset,
                                      object maker_balance,
                                      object market_pair,
                                      str trading_pair,
                                      object taker_balance,
                                      object hedge_amount,
                                      bint is_buy,
                                      object price
                                      ):

        if trading_pair in self._sb_order_tracker._tracked_limit_orders:
            return
        if self._last_trade_time[maker_asset] > self._current_timestamp - self._hedge_interval:
            return
        self._last_trade_time[maker_asset]=self._current_timestamp
        self.place_order(maker_asset, is_buy, abs(hedge_amount), price)

    cdef object place_order(self,
                            str maker_asset,
                            bint is_buy,
                            object amount,
                            object price):
        cdef:
            object market_pair = self._market_infos[maker_asset]
            str trading_pair = market_pair.trading_pair
            ExchangeBase market = market_pair.market
            object quantized_order_amount = market.c_quantize_order_amount(trading_pair, Decimal(amount))
        price = Decimal(price)
        price = price*(Decimal(1) + Decimal(self._slippage)) if is_buy else price*(Decimal(1) - Decimal(self._slippage))
        if quantized_order_amount*price>self._minimum_trade:
            if is_buy:
                order_id = self.c_buy_with_specific_market(market_pair, quantized_order_amount,
                                                           order_type=OrderType.LIMIT, price=price, expiration_seconds=NaN)
                if order_id:
                    self.update_shadow_position(trading_pair, quantized_order_amount)
            else:
                order_id = self.c_sell_with_specific_market(market_pair, quantized_order_amount,
                                                            order_type=OrderType.LIMIT, price=price, expiration_seconds=NaN)
                if order_id:
                    self.update_shadow_position(trading_pair, -quantized_order_amount)
            self.log_with_clock(logging.INFO,
                                f"Place {'Buy' if is_buy else 'Sell'} {quantized_order_amount} {trading_pair}")

    def update_wallet(self):
        data=[]
        # columns = ["Asset", "Hedge Price", self._exchanges[0].name,
        #            self._exchanges[1].name, "Diff", "qoute", "shadow_balance", "last_trade"]
        columns = ["Asset", "Price", "Maker", "Taker", "Diff", "Hedge Ratio"]
        for maker_asset in self._market_infos:
            market_pair = self._market_infos[maker_asset]
            trading_pair=market_pair.trading_pair
            # After a recent trade execution, the position returned may be 0 for some time (binance perpetual),
            # Hence, introduce minimum time prior to last trade to ensure update is correct
            # Added to ensure shadow balance can remain in sync with actual balance
            # collect necessary data to check hedge then continue the rest to minimize execution time.
            if self._last_trade_time[maker_asset]==0 or max(self._last_trade_time.values())<self._current_timestamp-self._update_shadow_balance_interval:
                taker_balance = self.get_position_amount(trading_pair)
                self.set_shadow_position(trading_pair, taker_balance)
            maker_balance = self.get_balance(maker_asset)
            taker_balance = self.get_shadow_position(trading_pair)
            hedge_amount = -(maker_balance*self._hedge_ratio + taker_balance)
            is_buy = hedge_amount > 0
            price = market_pair.get_price(is_buy)
            self.check_and_hedge_asset(maker_asset,
                                       maker_balance,
                                       market_pair,
                                       trading_pair,
                                       taker_balance,
                                       hedge_amount,
                                       is_buy,
                                       price)
            mid_price = market_pair.get_mid_price()
            difference = - (maker_balance + taker_balance)
            hedge_ratio = Decimal(-round(taker_balance/maker_balance, 2)) if maker_balance != 0 else 1
            data.append([
                maker_asset,
                mid_price,
                maker_balance,
                taker_balance,
                difference,
                hedge_ratio,
            ])
        self._wallet_df = pd.DataFrame(data=data, columns=columns)

    def active_positions_df(self) -> pd.DataFrame:
        columns = ["Symbol", "Type", "Entry Price", "Amount", "Leverage"]
        data = []
        for idx in self.active_positions.values():
            data.append([
                idx.trading_pair,
                idx.position_side.name,
                idx.entry_price,
                idx.amount,
                idx.leverage,
            ])

        return pd.DataFrame(data=data, columns=columns)

    def format_status(self) -> str:
        lines = []
        if not self._all_markets_ready:
            for exchange in self._exchanges:
                if not exchange.ready:
                    lines.extend(f"{exchange.name} connector is not ready...\n")
            return ''.join(lines)

        lines.extend(["", f"  Wallet:\n"])
        lines.extend(["    " + line for line in self._wallet_df.to_string(index=False).split("\n")])

        # See if there're any active positions.
        if len(self.active_positions) > 0:
            df = self.active_positions_df()
            lines.extend(["", "  Positions:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        else:
            lines.extend(["", "  No active positions."])

        return "\n".join(lines)

    cdef c_apply_initial_settings(self, object market_pair, object position, int64_t leverage):
        cdef:
            ExchangeBase market = market_pair.market
            str trading_pair = market_pair.trading_pair
        market.set_leverage(trading_pair, leverage)
        market.set_position_mode(position)

    cdef c_did_fill_order(self, object order_filled_event):
        cdef:
            str trading_pair = order_filled_event.trading_pair
            str trade_type = "Buy" if order_filled_event.trade_type == TradeType.BUY else "sell"
            object price = order_filled_event.price
            object amount = order_filled_event.amount
        self.log_with_clock(
            logging.INFO,
            f"{trading_pair} {trade_type} order of "
            f"{amount}  filled at {price}.")

    cdef c_start(self, Clock clock, double timestamp):
        clock._tick_size = min(self._hedge_interval, 1)
        StrategyBase.c_start(self, clock, timestamp)
        cdef:
            object market_pair
            str trading_pair
            object taker_balance
        self._last_timestamp = timestamp
        for maker_asset in self._market_infos:
            market_pair = self._market_infos[maker_asset]
            trading_pair = market_pair.trading_pair
            self._shadow_taker_balance[trading_pair]=0
            self._last_trade_time[maker_asset]=0
            self.c_apply_initial_settings(market_pair, self._position_mode, self._leverage)

    cdef c_tick(self, double timestamp):
        StrategyBase.c_tick(self, timestamp)
        cdef:
            int64_t current_tick = <int64_t>(timestamp // self._status_report_interval)
            int64_t last_tick = <int64_t>(self._last_timestamp // self._status_report_interval)
            bint should_report_warnings = (current_tick > last_tick)

        try:
            if not self._all_markets_ready:
                self._all_markets_ready = all([market.ready for market in self._sb_markets])
                if not self._all_markets_ready:
                    # Markets not ready yet. Don't do anything.
                    if should_report_warnings:
                        self.logger().warning(f"Markets are not ready. No market making trades are permitted.")
                    return
                else:
                    # Markets are ready, ok to proceed.
                    self.logger().info(f"Markets are ready. Trading started.")

            if should_report_warnings:
                # Check if all markets are still connected or not. If not, log a warning.
                if not all([market.network_status is NetworkStatus.CONNECTED for market in self._sb_markets]):
                    self.logger().warning(f"WARNING: Some markets are not connected or are down at the moment. Market "
                                          f"making may be dangerous when markets or networks are unstable.")

            self.update_wallet()

        finally:
            self._last_timestamp=timestamp

    cdef c_did_complete_buy_order(self, object order_completed_event):
        """
        Output log message when a bid order (on maker side or taker side) is completely taken.
        :param order_completed_event: event object
        """
        cdef:
            str order_id = order_completed_event.order_id
            object order_type = order_completed_event.order_type
            object base_asset_amount = order_completed_event.base_asset_amount
            object quote_asset_amount = order_completed_event.quote_asset_amount
            str base_asset = order_completed_event.base_asset
            str quote_asset = order_completed_event.quote_asset

        self.log_with_clock(
            logging.INFO,
            f"{order_type} order {order_id} "
            f"({base_asset_amount} {base_asset} @ "
            f"{quote_asset_amount} {quote_asset}) has been completely filled."
        )
        self.notify_hb_app_with_timestamp(
            f"{order_type} order {order_id} "
            f"({base_asset_amount} {base_asset} @ "
            f"{quote_asset_amount} {quote_asset}) has been completely filled."
        )

    cdef c_did_complete_sell_order(self, object order_completed_event):
        """
        Output log message when a ask order (on maker side or taker side) is completely taken.
        :param order_completed_event: event object
        """
        cdef:
            str order_id = order_completed_event.order_id
            object order_type = order_completed_event.order_type
            object base_asset_amount = order_completed_event.base_asset_amount
            object quote_asset_amount = order_completed_event.quote_asset_amount
            str base_asset = order_completed_event.base_asset
            str quote_asset = order_completed_event.quote_asset

        self.log_with_clock(
            logging.INFO,
            f"{order_type} order {order_id} "
            f"({base_asset_amount} {base_asset} @ "
            f"{quote_asset_amount} {quote_asset}) has been completely filled."
        )
        self.notify_hb_app_with_timestamp(
            f"{order_type} order {order_id} "
            f"({base_asset_amount} {base_asset} @ "
            f"{quote_asset_amount} {quote_asset}) has been completely filled."
        )
