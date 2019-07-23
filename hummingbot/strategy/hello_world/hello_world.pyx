# distutils: language=c++
from decimal import Decimal
import logging
from typing import (
    List,
    Tuple,
    Optional,
    Dict
)

from hummingbot.core.clock cimport Clock
from hummingbot.logger import HummingbotLogger
from hummingbot.core.event.event_listener cimport EventListener
from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.market.market_base import (
    MarketBase,
    OrderType
)

from hummingbot.strategy.market_symbol_pair import MarketSymbolPair
from hummingbot.strategy.strategy_base import StrategyBase

from libc.stdint cimport int64_t
from hummingbot.core.data_type.order_book cimport OrderBook

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
    OPTION_LOG_NULL_ORDER_SIZE = 1 << 0
    OPTION_LOG_REMOVING_ORDER = 1 << 1
    OPTION_LOG_ADJUST_ORDER = 1 << 2
    OPTION_LOG_CREATE_ORDER = 1 << 3
    OPTION_LOG_MAKER_ORDER_FILLED = 1 << 4
    OPTION_LOG_STATUS_REPORT = 1 << 5
    OPTION_LOG_MAKER_ORDER_HEDGED = 1 << 6
    OPTION_LOG_ALL = 0x7fffffffffffffff
    CANCEL_EXPIRY_DURATION = 60.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global ds_logger
        if ds_logger is None:
            ds_logger = logging.getLogger(__name__)
        return ds_logger

    #TODO: Add more logging, remove all warnings for PEP and use Decimal everywhere
    def __init__(self,
                 market_infos: List[MarketSymbolPair],
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
            (market_info.market, market_info.trading_pair): market_info
            for market_info in market_infos
        }
        self._tracked_orders = {}
        self._all_markets_ready = False
        self._place_orders = True
        self._logging_options = logging_options
        self._status_report_interval = status_report_interval
        self._order_id_to_market_info = {}
        self._in_flight_cancels = {}
        self._time_delay = time_delay
        self._time_to_cancel = {}
        self._cancel_order_wait_time = cancel_order_wait_time
        self._order_type = order_type
        if order_price is not None:
            self._order_price = order_price
        self._is_buy = is_buy
        self._order_amount = order_amount

        cdef:
            set all_markets = set([market_info.market for market_info in market_infos])

        self.c_add_markets(list(all_markets))

    @property
    def active_bids(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return [(market, limit_order) for market, limit_order in self.active_maker_orders if limit_order.is_buy]

    @property
    def active_asks(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return [(market, limit_order) for market, limit_order in self.active_maker_orders if not limit_order.is_buy]

    @property
    def active_maker_orders(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return [
            (market_info.market, order)
            for market_info, orders_map in self._tracked_orders.items()
            for order in orders_map.values()
        ]

    @property
    def market_info_to_active_orders(self) -> Dict[MarketSymbolPair, List[LimitOrder]]:
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

    @property
    def place_orders(self):
        return self._place_orders

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
            active_orders = self.market_info_to_active_orders.get(market_info, [])

            warning_lines.extend(self.network_warning([market_info]))

            markets_df = self.market_status_data_frame([market_info])
            lines.extend(["", "  Markets:"] + ["    " + line for line in str(markets_df).split("\n")])

            assets_df = self.wallet_balance_data_frame([market_info])
            lines.extend(["", "  Assets:"] + ["    " + line for line in str(assets_df).split("\n")])

            # See if there're any open orders.
            if len(active_orders) > 0:
                df = LimitOrder.to_pandas(active_orders)
                df_lines = str(df).split("\n")
                lines.extend(["", "  Active orders:"] +
                             ["    " + line for line in df_lines])
            else:
                lines.extend(["", "  No active maker orders."])

            warning_lines.extend(self.balance_warning([market_info]))

        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    cdef c_did_fail_order(self, object order_failed_event):
        cdef:
            str order_id = order_failed_event.order_id
            object market_info= self._order_id_to_market_info.get(order_id)

        self.logger().info(f"Order: {order_id} for {market_info.trading_pair} has been failed")
        self.c_stop_tracking_order(market_info, order_id)

    cdef c_did_cancel_order(self, object cancelled_event):
        cdef:
            str order_id = cancelled_event.order_id
            object market_info = self._order_id_to_market_info.get(order_id)

        self.logger().info(f"Order: {order_id} for {market_info.trading_pair} has been succesfully cancelled")
        self.c_stop_tracking_order(market_info, order_id)

    cdef c_did_fill_order(self, object order_filled_event):
        cdef:
            str order_id = order_filled_event.order_id
            object market_info = self._order_id_to_market_info.get(order_id)

        self.logger().info(f"Order: {order_id} for {market_info.trading_pair} has been filled")
        self.c_stop_tracking_order(market_info, order_id)

    cdef c_did_complete_buy_order(self, object order_completed_event):
        cdef:
            str order_id = order_completed_event.order_id
            object market_info = self._order_id_to_market_info.get(order_id)

        self.logger().info(f"Buy Order: {order_id} for {market_info.trading_pair} has been completely filled")
        self.c_stop_tracking_order(market_info, order_id)

    cdef c_did_complete_sell_order(self, object order_completed_event):
        cdef:
            str order_id = order_completed_event.order_id
            object market_info = self._order_id_to_market_info.get(order_id)

        self.logger().info(f"Sell Order: {order_id} for {market_info.trading_pair} has been completely filled")
        self.c_stop_tracking_order(market_info, order_id)

    cdef c_cancel_order(self, object market_info, str order_id):
        cdef:
            MarketBase market = market_info.market
            list keys_to_delete = []

        # Maintain the cancel expiry time invariant.
        for k, cancel_timestamp in self._in_flight_cancels.items():
            if cancel_timestamp < self._current_timestamp - self.CANCEL_EXPIRY_DURATION:
                keys_to_delete.append(k)
        for k in keys_to_delete:
            del self._in_flight_cancels[k]

        if order_id in self._in_flight_cancels:
            return

        # Track the cancel and tell maker market to cancel the order.
        self._in_flight_cancels[order_id] = self._current_timestamp
        market.c_cancel(market_info.trading_pair, order_id)

    cdef c_start(self, Clock clock, double timestamp):
        StrategyBase.c_start(self, clock, timestamp)
        self.logger().info(f"Waiting for {self._time_delay} to place orders")
        self._start_timestamp = timestamp
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
                self._all_markets_ready = all([market.ready for market in self._sb_markets])
                if not self._all_markets_ready:
                    # Markets not ready yet. Don't do anything.
                    if should_report_warnings:
                        self.logger().warning(f"Markets are not ready. No market making trades are permitted.")
                    return

            if should_report_warnings:
                if not all([market.network_status is NetworkStatus.CONNECTED for market in self._sb_markets]):
                    self.logger().warning(f"WARNING: Some markets are not connected or are down at the moment. Market "
                                          f"making may be dangerous when markets or networks are unstable.")

            market_info_to_active_orders = self.market_info_to_active_orders

            for market_info in self._market_infos.values():
                self.c_process_market(market_info)
        finally:
            self._last_timestamp = timestamp

    cdef c_start_tracking_order(self, object market_info, str order_id, bint is_buy, object price, object quantity):
        self.logger().info(f"The bot is tracking the order {order_id}")
        if market_info not in self._tracked_orders:
            self._tracked_orders[market_info] = {}

        cdef:
            LimitOrder limit_order = LimitOrder(order_id,
                                                market_info.trading_pair,
                                                is_buy,
                                                market_info.base_asset,
                                                market_info.quote_asset,
                                                float(price),
                                                float(quantity))
        self._tracked_orders[market_info][order_id] = limit_order
        self._order_id_to_market_info[order_id] = market_info

    cdef c_stop_tracking_order(self, object market_info, str order_id):
        if market_info in self._tracked_orders and order_id in self._tracked_orders[market_info]:
            self.logger().info(f"The bot has stopped tracking the order {order_id}")
            del self._tracked_orders[market_info][order_id]
            if len(self._tracked_orders[market_info]) < 1:
                del self._tracked_orders[market_info]
        if order_id in self._order_id_to_market_info:
            del self._order_id_to_market_info[order_id]

    cdef c_place_orders(self, object market_info):
        self.logger().info(f"Checking to see if the user has enough balance to place orders")
        if self.c_has_enough_balance(market_info):

            if self._order_type == "market":
                if self._is_buy:
                    order_id = self.c_buy_with_specific_market(market_info,
                                                               amount = self._order_amount)
                    self.logger().info("Market buy order has been executed")
                else:
                    order_id = self.c_sell_with_specific_market(market_info,
                                                                amount = self._order_amount)
                    self.logger().info("Market sell order has been executed")
            else:
                if self._is_buy:
                    order_id = self.c_buy_with_specific_market(market_info,
                                                               amount = self._order_amount,
                                                               order_type = OrderType.LIMIT,
                                                               price = self._order_price)
                    self.logger().info("Limit buy order has been placed")

                else:
                    order_id = self.c_sell_with_specific_market(market_info,
                                                                amount = self._order_amount,
                                                                order_type = OrderType.LIMIT,
                                                                price = self._order_price)
                    self.logger().info("Limit sell order has been placed")

                self.c_start_tracking_order(market_info, order_id, self._is_buy, self._order_price, self._order_amount)
                self._time_to_cancel[order_id] = self._current_timestamp + self._cancel_order_wait_time
        else:
            self.logger().info(f"Not enough balance to run the strategy. Please check balances and try again.")


    cdef c_has_enough_balance(self, object market_info):
        cdef:
            MarketBase market = market_info.market
            double base_asset_balance = market.c_get_balance(market_info.base_asset)
            double quote_asset_balance = market.c_get_balance(market_info.quote_asset)
            OrderBook order_book = market_info.order_book
            double price = order_book.c_get_price_for_volume(True, self._order_amount).result_price

        return quote_asset_balance >= self._order_amount * price if self._is_buy else base_asset_balance >= self._order_amount


    cdef c_process_market(self, object market_info):
        cdef:
            MarketBase maker_market = market_info.market
            set cancel_order_ids = set()

        if self._place_orders:

            #If current timestamp is greater than the start timestamp + time delay place orders
            if self._current_timestamp > self._start_timestamp + self._time_delay:

                self._place_orders = False
                self.logger().info(f"Current timestamp: {self._current_timestamp} is greater than "
                                   f"Start timestamp:{self._start_timestamp} with time delay: {self._time_delay} ")
                self.c_place_orders(market_info)

        active_orders = self.market_info_to_active_orders[market_info]

        if len(active_orders) >0 :
            for active_order in active_orders:
                if self._current_timestamp >= self._time_to_cancel[active_order.client_order_id]:
                    cancel_order_ids.add(active_order.client_order_id)

        if len(cancel_order_ids) > 0:

            for order in cancel_order_ids:
                self.c_cancel_order(market_info, order)


