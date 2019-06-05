from collections import (
    defaultdict,
    deque,
    OrderedDict
)
from decimal import Decimal
import logging
import pandas as pd
from typing import (
    List,
    Tuple,
    Optional
)

from hummingbot.core.clock cimport Clock
from hummingbot.core.event.events import (
    MarketEvent,
    TradeType
)
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

from .data_types import MarketInfo
from .order_filter_delegate import OrderFilterDelegate
from .order_pricing_delegate import OrderPricingDelegate
from .order_sizing_delegate import OrderSizingDelegate

NaN = float("nan")
s_decimal_zero = Decimal(0)
s_logger = None


cdef class BasePureMakingStrategyEventListener(EventListener):
    cdef:
        PureMarketMakingStrategyV2 _owner

    def __init__(self, PureMarketMakingStrategyV2 owner):
        super().__init__()
        self._owner = owner


cdef class BuyOrderCompletedListener(BasePureMakingStrategyEventListener):
    cdef c_call(self, object arg):
        self._owner.c_did_complete_buy_order(arg)


cdef class SellOrderCompletedListener(BasePureMakingStrategyEventListener):
    cdef c_call(self, object arg):
        self._owner.c_did_complete_sell_order(arg)


cdef class OrderFilledListener(BasePureMakingStrategyEventListener):
    cdef c_call(self, object arg):
        self._owner.c_did_fill_order(arg)


cdef class OrderFailedListener(BasePureMakingStrategyEventListener):
    cdef c_call(self, object arg):
        self._owner.c_did_fail_order(arg)


cdef class OrderCancelledListener(BasePureMakingStrategyEventListener):
    cdef c_call(self, object arg):
        self._owner.c_did_cancel_order(arg)


cdef class OrderExpiredListener(BasePureMakingStrategyEventListener):
    cdef c_call(self, object arg):
        self._owner.c_did_cancel_order(arg)


cdef class PureMarketMakingStrategyV2(StrategyBase):
    BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled.value
    ORDER_EXPIRED_EVENT_TAG = MarketEvent.OrderExpired.value
    TRANSACTION_FAILURE_EVENT_TAG = MarketEvent.TransactionFailure.value

    OPTION_LOG_NULL_ORDER_SIZE = 1 << 0
    OPTION_LOG_REMOVING_ORDER = 1 << 1
    OPTION_LOG_ADJUST_ORDER = 1 << 2
    OPTION_LOG_CREATE_ORDER = 1 << 3
    OPTION_LOG_MAKER_ORDER_FILLED = 1 << 4
    OPTION_LOG_STATUS_REPORT = 1 << 5
    OPTION_LOG_MAKER_ORDER_HEDGED = 1 << 6
    OPTION_LOG_ALL = 0x7fffffffffffffff

    ORDER_ADJUST_SAMPLE_INTERVAL = 5
    ORDER_ADJUST_SAMPLE_WINDOW = 12

    SHADOW_MAKER_ORDER_KEEP_ALIVE_DURATION = 60.0
    CANCEL_EXPIRY_DURATION = 60.0

    # These are exchanges where you're expected to expire orders instead of actively cancelling them.
    RADAR_RELAY_TYPE_EXCHANGES = {"radar_relay", "bamboo_relay"}

    @classmethod
    def logger(cls):
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self, market_infos: List[MarketInfo],
                 filter_delegate: Optional[OrderFilterDelegate] = None,
                 pricing_delegate: Optional[OrderPricingDelegate] = None,
                 sizing_delegate: Optional[OrderSizingDelegate] = None,
                 cancel_order_wait_time: float = 60,
                 logging_options: int = OPTION_LOG_ALL,
                 limit_order_min_expiration: float = 130.0,
                 status_report_interval: float = 900):
        if len(market_infos) < 1:
            raise ValueError(f"market_infos must not be empty.")

        super().__init__()
        self._market_infos = {
            (market_info.market, market_info.symbol): market_info
            for market_info in market_infos
        }
        self._markets = set([market_info.market for market_info in market_infos])
        self._all_markets_ready = False
        self._cancel_order_wait_time = cancel_order_wait_time
        # For tracking limit orders
        self._tracked_maker_orders = {}
        # Preserving a copy of limit orders for safety for sometime
        self._shadow_tracked_maker_orders = {}
        self._order_id_to_market_info = {}
        self._shadow_order_id_to_market_info = {}
        # For cleaning up limit orders
        self._shadow_gc_requests = deque()
        self._time_to_cancel = {}
        self._in_flight_cancels = {}

        self._logging_options = logging_options
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self._limit_order_min_expiration = limit_order_min_expiration

        # TODO: if these are None, put in some default plugins that trade conservatively.
        self._filter_delegate = filter_delegate
        self._pricing_delegate = pricing_delegate
        self._sizing_delegate = sizing_delegate
        self._delegate_lock = False

        self._buy_order_completed_listener = BuyOrderCompletedListener(self)
        self._sell_order_completed_listener = SellOrderCompletedListener(self)
        self._order_filled_listener = OrderFilledListener(self)
        self._order_failed_listener = OrderFailedListener(self)
        self._order_cancelled_listener = OrderCancelledListener(self)
        self._order_expired_listener = OrderExpiredListener(self)

        cdef:
            MarketBase typed_market

        for market in self._markets:
            typed_market = market
            typed_market.c_add_listener(self.BUY_ORDER_COMPLETED_EVENT_TAG, self._buy_order_completed_listener)
            typed_market.c_add_listener(self.SELL_ORDER_COMPLETED_EVENT_TAG, self._sell_order_completed_listener)
            typed_market.c_add_listener(self.ORDER_FILLED_EVENT_TAG, self._order_filled_listener)
            typed_market.c_add_listener(self.ORDER_CANCELLED_EVENT_TAG, self._order_cancelled_listener)
            typed_market.c_add_listener(self.ORDER_EXPIRED_EVENT_TAG, self._order_expired_listener)
            typed_market.c_add_listener(self.TRANSACTION_FAILURE_EVENT_TAG, self._order_failed_listener)

    @property
    def active_markets(self) -> List[MarketBase]:
        return list(self._markets)

    @property
    def active_maker_orders(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return [
            (market_info.market, limit_order)
            for market_info, orders_map in self._tracked_maker_orders.items()
            for limit_order in orders_map.values()
        ]

    @property
    def logging_options(self) -> int:
        return self._logging_options

    @logging_options.setter
    def logging_options(self, int64_t logging_options):
        self._logging_options = logging_options

    @property
    def filter_delegate(self) -> OrderFilterDelegate:
        return self._filter_delegate

    @property
    def pricing_delegate(self) -> OrderPricingDelegate:
        return self._pricing_delegate

    @property
    def sizing_delegate(self) -> OrderSizingDelegate:
        return self._sizing_delegate

    def log_with_clock(self, log_level: int, msg: str, **kwargs):
        clock_timestamp = pd.Timestamp(self._current_timestamp, unit="s", tz="UTC")
        self.logger().log(log_level, f"{msg} [clock={str(clock_timestamp)}]", **kwargs)

    def format_status(self) -> str:
        pass

    # The following exposed Python functions are meant for unit tests
    # ---------------------------------------------------------------

    def create_new_orders(self, market_info: MarketInfo):
        return self.c_create_new_orders(market_info)

    def cancel_order(self, market_info: MarketInfo, order_id:str):
        return self.c_cancel_order(market_info, order_id)
    # ---------------------------------------------------------------

    cdef c_buy_with_specific_market(self, MarketBase market, str symbol, double amount,
                                    double price,
                                    object order_type = OrderType.LIMIT,
                                    double expiration_seconds = NaN):
        if self._delegate_lock:
            raise RuntimeError("Delegates are not allowed to execute orders directly.")

        cdef:
            dict kwargs = {
                "expiration_ts": self._current_timestamp + max(self._limit_order_min_expiration, expiration_seconds)
            }

        if market not in self._markets:
            raise ValueError(f"market object for buy order is not in the whitelisted markets set.")
        return market.c_buy(symbol, amount, order_type=order_type, price=price, kwargs=kwargs)

    cdef c_sell_with_specific_market(self, MarketBase market, str symbol, double amount,
                                     double price,
                                     object order_type = OrderType.LIMIT,
                                     double expiration_seconds = NaN):
        if self._delegate_lock:
            raise RuntimeError("Delegates are not allowed to execute orders directly.")

        cdef:
            dict kwargs = {
                "expiration_ts": self._current_timestamp + max(self._limit_order_min_expiration, expiration_seconds)
            }

        if market not in self._markets:
            raise ValueError(f"market object for sell order is not in the whitelisted markets set.")
        return market.c_sell(symbol, amount, order_type=order_type, price=price, kwargs=kwargs)

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

        # Track the cancel and tell maker market to cancel the order.
        self._in_flight_cancels[order_id] = self._current_timestamp
        market.c_cancel(market.symbol, order_id)

    cdef c_start(self, Clock clock, double timestamp):
        StrategyBase.c_start(self, clock, timestamp)
        self._last_timestamp = timestamp

    cdef c_tick(self, double timestamp):
        StrategyBase.c_tick(self, timestamp)

    cdef c_process_market_info(self, object market_info, list active_maker_orders):
        pass

    cdef c_did_fill_order(self, object order_filled_event):
        pass

    cdef c_did_fail_order(self, object order_failed_event):
        pass

    cdef c_did_cancel_order(self, object cancelled_evnet):
        pass

    cdef c_did_complete_buy_order(self, object order_completed_event):
        pass

    cdef c_did_complete_sell_order(self, object order_completed_event):
        pass

    cdef c_start_tracking_order(self, object market_info, str order_id, bint is_buy, object price, object quantity):
        pass

    cdef c_stop_tracking_order(self, object market_info, str order_id):
        pass

    cdef c_check_and_cleanup_shadow_records(self):
        pass

    cdef c_create_new_orders(self, object market_info):
        pass