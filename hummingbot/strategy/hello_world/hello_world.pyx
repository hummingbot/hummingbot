# distutils: language=c++
from collections import deque
from decimal import Decimal
import logging
import pandas as pd
from typing import (
    List,
    Tuple,
    Optional,
    Dict
)

from hummingbot.core.clock cimport Clock
from hummingbot.core.event.events import (
    MarketEvent,
    TradeType
)


from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.hello_world.hello_world_market_pair import HelloWorldMarketPair
from hummingbot.core.event.event_listener cimport EventListener
from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.market.market_base import (
    MarketBase,
    OrderType
)
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.strategy.strategy_base import StrategyBase

from .data_types import (
    MarketInfo
)
from libc.stdint cimport int64_t
from hummingbot.core.data_type.order_book cimport OrderBook
import itertools

NaN = float("nan")
s_decimal_zero = Decimal(0)
ds_logger = None

cdef class HelloWorldStrategyEventListener(EventListener):
    cdef:
        HelloWorldStrategy _owner

    def __init__(self, HelloWorldStrategy owner):
        super().__init__()
        self._owner = owner


cdef class BuyOrderCompletedListener(HelloWorldStrategyEventListener):
    cdef c_call(self, object arg):
        self._owner.c_did_complete_buy_order(arg)


cdef class SellOrderCompletedListener(HelloWorldStrategyEventListener):
    cdef c_call(self, object arg):
        self._owner.c_did_complete_sell_order(arg)


cdef class OrderFilledListener(HelloWorldStrategyEventListener):
    cdef c_call(self, object arg):
        self._owner.c_did_fill_order(arg)


cdef class OrderFailedListener(HelloWorldStrategyEventListener):
    cdef c_call(self, object arg):
        self._owner.c_did_fail_order(arg)


cdef class OrderCancelledListener(HelloWorldStrategyEventListener):
    cdef c_call(self, object arg):
        self._owner.c_did_cancel_order(arg)

cdef class OrderExpiredListener(HelloWorldStrategyEventListener):
    cdef c_call(self, object arg):
        self._owner.c_did_cancel_order(arg)

cdef class HelloWorldStrategy(StrategyBase):
    BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled.value
    ORDER_EXPIRED_EVENT_TAG = MarketEvent.OrderExpired.value
    ORDER_FAILURE_EVENT_TAG = MarketEvent.OrderFailure.value
    OPTION_LOG_STATUS_REPORT = 1 << 0
    OPTION_LOG_ALL = 0xfffffffffffffff

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global ds_logger
        if ds_logger is None:
            ds_logger = logging.getLogger(__name__)
        return ds_logger

    def __init__(self,
                 market_infos: List[MarketInfo],
                 order_type: str = "limit",
                 order_price: Optional[float] = None,
                 cancel_order_wait_time: float = 60.0,
                 is_buy: bool = True,
                 time_delay: float = 10.0,
                 order_amount: float = 1.0,
                 logging_options: int = OPTION_LOG_ALL,
                 status_report_interval: float = 900):

        if len(market_infos) < 1:
            raise ValueError(f"market_infos must not be empty.")

        super().__init__()
        self._market_infos = {
            (market_info.market, market_info.symbol): market_info
            for market_info in market_infos
        }

        self._markets = set([market_info.market for market_info in market_infos])
        self._tracked_orders = {}
        self._all_markets_ready = False
        self.place_orders = True
        self._logging_options = logging_options
        self._status_report_interval = status_report_interval
        self._order_id_to_market_info = {}
        self._start_timestamp = self._current_timestamp
        self._time_delay = time_delay
        self._time_to_cancel = {}
        self._cancel_order_wait_time = cancel_order_wait_time

        self._buy_order_completed_listener = BuyOrderCompletedListener(self)
        self._sell_order_completed_listener = SellOrderCompletedListener(self)
        self._order_filled_listener = OrderFilledListener(self)
        self._order_failed_listener = OrderFailedListener(self)
        self._order_cancelled_listener = OrderCancelledListener(self)
        self._order_expired_listener = OrderExpiredListener(self)
        self._order_type = order_type
        self._order_price = order_price
        self._is_buy = is_buy
        self._order_amount = order_amount

        cdef:
            MarketBase typed_market

        for market in self._markets:
            typed_market = market
            typed_market.c_add_listener(self.BUY_ORDER_COMPLETED_EVENT_TAG, self._buy_order_completed_listener)
            typed_market.c_add_listener(self.SELL_ORDER_COMPLETED_EVENT_TAG, self._sell_order_completed_listener)
            typed_market.c_add_listener(self.ORDER_FILLED_EVENT_TAG, self._order_filled_listener)
            typed_market.c_add_listener(self.ORDER_CANCELLED_EVENT_TAG, self._order_cancelled_listener)
            typed_market.c_add_listener(self.ORDER_EXPIRED_EVENT_TAG, self._order_expired_listener)
            typed_market.c_add_listener(self.ORDER_FAILURE_EVENT_TAG, self._order_failed_listener)

    @property
    def active_markets(self) -> List[MarketBase]:
        return list(self._markets)

    @property
    def active_maker_orders(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return [
            (market_info.market, order)
            for market_info, orders_map in self._tracked_orders.items()
            for order in orders_map.values()
        ]

    @property
    def market_info_to_active_orders(self) -> Dict[MarketInfo, List[LimitOrder]]:
        return {
            market_info: [
                order
                for order in self._tracked_orders.get(market_info, {}).values()
            ]
            for market_info
            in self._market_infos.values()
        }

    @property
    def logging_options(self) -> int:
        return self._logging_options

    @logging_options.setter
    def logging_options(self, int64_t logging_options):
        self._logging_options = logging_options


    def format_status(self) -> str:
        cdef:
            MarketBase maker_market
            OrderBook maker_order_book
            str maker_symbol
            str maker_base
            str maker_quote
            double maker_base_balance
            double maker_quote_balance
            list lines = []
            list warning_lines = []
            dict market_info_to_active_orders = self.market_info_to_active_orders
            list active_orders = []

        for market_info in self._market_infos.values():
            # Get some basic info about the market pair.
            maker_market = market_info.market
            maker_symbol = market_info.symbol
            maker_name = maker_market.name
            maker_base = market_info.base_currency
            maker_quote = market_info.quote_currency
            maker_order_book = maker_market.c_get_order_book(maker_symbol)
            maker_base_balance = maker_market.c_get_balance(maker_base)
            maker_quote_balance = maker_market.c_get_balance(maker_quote)
            bid_price = maker_order_book.c_get_price(False)
            ask_price = maker_order_book.c_get_price(True)
            active_orders = market_info_to_active_orders.get(market_info, [])

            if not maker_market.network_status is NetworkStatus.CONNECTED:
                warning_lines.extend([
                    f"  Markets are offline for the {maker_symbol} pair. Continued market making "
                    f"with these markets may be dangerous.",
                    ""
                ])

            markets_columns = ["Market", "Symbol", "Bid Price", "Ask Price"]
            markets_data = [
                [maker_name, maker_symbol, bid_price, ask_price],
            ]
            markets_df = pd.DataFrame(data=markets_data, columns=markets_columns)
            lines.extend(["", "  Markets:"] + ["    " + line for line in str(markets_df).split("\n")])

            assets_columns = ["Market", "Asset", "Balance"]
            assets_data = [
                [maker_name, maker_base, maker_base_balance],
                [maker_name, maker_quote, maker_quote_balance],
            ]
            assets_df = pd.DataFrame(data=assets_data, columns=assets_columns)
            lines.extend(["", "  Assets:"] + ["    " + line for line in str(assets_df).split("\n")])

            # See if there're any open orders.
            if len(active_orders) > 0:
                df = LimitOrder.to_pandas(active_orders)
                df_lines = str(df).split("\n")
                lines.extend(["", "  Active orders:"] +
                             ["    " + line for line in df_lines])
            else:
                lines.extend(["", "  No active open orders."])

            # Add warning lines on null balances.
            if maker_base_balance <= 0:
                warning_lines.append(f"  Maker market {maker_base} balance is 0. No ask order is possible.")
            if maker_quote_balance <= 0:
                warning_lines.append(f"  Maker market {maker_quote} balance is 0. No bid order is possible.")

        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    cdef c_did_fail_order(self, object order_failed_event):
        cdef:
            str order_id = order_failed_event.order_id
            object market_info= self._order_id_to_market_info.get(order_id)

        self.logger().info("Order has failed. Trying to place it again.")
        self.place_orders = True

    cdef c_did_cancel_order(self, object cancelled_event):
        cdef:
            str order_id = cancelled_event.order_id
            object market_info = self._order_id_to_market_info.get(order_id)

        self.logger().info(f"Order: {order_id} for {market_info.symbol} has been succesfully cancelled")

    cdef c_did_fill_order(self, object order_filled_event):
        cdef:
            str order_id = order_filled_event.order_id
            object market_info = self._order_id_to_market_info.get(order_id)

        self.logger().info(f"Order: {order_id} for {market_info.symbol} has been filled")

    cdef c_did_complete_buy_order(self, object order_completed_event):
        cdef:
            str order_id = order_completed_event.order_id
            object market_info = self._order_id_to_market_info.get(order_id)

        self.logger().info(f"Buy Order: {order_id} for {market_info.symbol} has been completely filled")

    cdef c_did_complete_sell_order(self, object order_completed_event):
        cdef:
            str order_id = order_completed_event.order_id
            object market_info = self._order_id_to_market_info.get(order_id)

        self.logger().info(f"Sell Order: {order_id} for {market_info.symbol} has been completely filled")

    cdef c_cancel_order(self, object market_info, str order_id):
        cdef:
            MarketBase market = market_info.market

        market.c_cancel(market_info.symbol, order_id)

    cdef c_start(self, Clock clock, double timestamp):
        StrategyBase.c_start(self, clock, timestamp)
        self._last_timestamp = timestamp

    cdef c_tick(self, double timestamp):
        StrategyBase.c_tick(self, timestamp)
        cdef:
            int64_t current_tick = <int64_t>(timestamp // self._status_report_interval)
            int64_t last_tick = <int64_t>(self._last_timestamp // self._status_report_interval)
            bint should_report_warnings = ((current_tick > last_tick) and
                                           (self._logging_options & self.OPTION_LOG_STATUS_REPORT))
            list active_maker_orders = self.active_maker_orders

        try:
            if not self._all_markets_ready:
                self._all_markets_ready = all([market.ready for market in self._markets])
                if not self._all_markets_ready:
                    # Markets not ready yet. Don't do anything.
                    if should_report_warnings:
                        self.logger().warning(f"Markets are not ready. No market making trades are permitted.")
                    return

            if should_report_warnings:
                if not all([market.network_status is NetworkStatus.CONNECTED for market in self._markets]):
                    self.logger().warning(f"WARNING: Some markets are not connected or are down at the moment. Market "
                                          f"making may be dangerous when markets or networks are unstable.")

            market_info_to_active_orders = self.market_info_to_active_orders

            for market_info in self._market_infos.values():
                self.c_process_market(market_info)
        finally:
            self._last_timestamp = timestamp

    cdef c_place_orders(self, object market_info):
        cdef:
            MarketBase market = market_info.market
            str symbol = market_info.symbol

        if self.c_has_enough_balance(market_info):
            if self._is_buy:
                if self._order_type == "market":
                    order_id = self.c_buy_with_specific_market(market,
                                                               amount = self._order_amount)
                else:
                    order_id = self.c_buy_with_specific_market(market,
                                                               amount = self._order_amount,
                                                               order_type = OrderType.LIMIT,
                                                               price = self._order_price)
            else:
                if self._order_type == "market":
                    order_id = self.c_sell_with_specific_market(market,
                                                               amount = self._order_amount)
                else:
                    order_id = self.c_sell_with_specific_market(market,
                                                                amount = self._order_amount,
                                                                order_type = OrderType.LIMIT,
                                                                price = self._order_price)
        self._order_id_to_market_info[order_id] = market_info
        self._time_to_cancel[order_id] = self._current_timestamp + self._cancel_order_wait_time


    cdef c_has_enough_balance(self, object market_info):
        cdef:
            MarketBase market = market_info.market
            str symbol = market_info.symbol
            double base_asset_balance = market.c_get_balance(market_info.base_currency)
            double quote_asset_balance = market.c_get_balance(market_info.quote_currency)
            OrderBook order_book = market.c_get_order_book(symbol)
            double price = order_book.c_get_price_for_volume(True, self._order_amount).result_price

        return quote_asset_balance >= self._order_amount * price if self._is_buy else base_asset_balance >= self._order_amount


    cdef c_process_market(self, object market_info):
        cdef:
            MarketBase maker_market = market_info.market
            list cancel_order_ids = []

        if self.place_orders:
            #self._start_time_delay_timestamp = min(self._current_timestamp, self._start_time_delay_timestamp)
            #Time is now greater than delay + start_timestamp
            #if self._current_timestamp > self._start_time_delay_timestamp + self._time_delay:
            if self._current_timestamp > self._start_timestamp + self._time_delay:
                self.place_orders = False
                self.c_place_orders(market_info)

        active_orders = self.market_info_to_active_orders[market_info]
        if len(active_orders) >0 :
            for active_order in active_orders:
                if self._current_timestamp >= self._time_to_cancel[active_order.client_order_id]:
                    cancel_order_ids.append(active_order.client_order_id)

        if len(cancel_order_ids) > 0:
                self.logger().info("Cancelling order")
                for order in cancel_order_ids:
                    self.c_cancel_order(market_info, order)


