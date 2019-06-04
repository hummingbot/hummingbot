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
    Tuple
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

    @classmethod
    def logger(cls):
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self, market_infos: List[MarketInfo],
                 order_size: float = 1.0,
                 bid_place_threshold: float = 0.01,
                 ask_place_threshold: float = 0.01,
                 cancel_order_wait_time: float = 60,
                 logging_options: int = OPTION_LOG_ALL,
                 limit_order_min_expiration: float = 130.0,
                 status_report_interval: float = 900):
        super().__init__()

        self._logging_options = logging_options
        self._last_timestamp = 0

    @property
    def active_markets(self) -> List[MarketBase]:
        pass

    @property
    def active_maker_orders(self) -> List[Tuple[MarketBase, LimitOrder]]:
        pass

    @property
    def logging_options(self) -> int:
        return self._logging_options

    @logging_options.setter
    def logging_options(self, int64_t logging_options):
        self._logging_options = logging_options

    @property
    def filter_delegate(self) -> OrderFilterDelegate:
        pass

    @property
    def pricing_delegate(self) -> OrderPricingDelegate:
        pass

    @property
    def sizing_delegate(self) -> OrderSizingDelegate:
        pass

    def log_with_clock(self, log_level: int, msg: str, **kwargs):
        clock_timestamp = pd.Timestamp(self._current_timestamp, unit="s", tz="UTC")
        self.logger().log(log_level, f"{msg} [clock={str(clock_timestamp)}]", **kwargs)

    def format_status(self) -> str:
        pass

    # The following exposed Python functions are meant for unit tests
    # ---------------------------------------------------------------

    def check_if_sufficient_balance(self, market_info: MarketInfo) -> bool:
        return self.c_check_if_sufficient_balance(market_info)

    def create_new_orders(self, market_info: MarketInfo):
        return self.c_create_new_orders(market_info)

    def cancel_order(self, market_info: MarketInfo,order_id:str):
        return self.c_cancel_order(market_info, order_id)
    # ---------------------------------------------------------------

    cdef c_buy_with_specific_market(self, MarketBase market, str symbol, double amount,
                                    double price,
                                    object order_type = OrderType.LIMIT,
                                    double expiration_seconds = NaN):
        pass

    cdef c_sell_with_specific_market(self, MarketBase market, str symbol, double amount,
                                     double price,
                                     object order_type = OrderType.LIMIT,
                                     double expiration_seconds = NaN):
        pass

    cdef c_cancel_order(self, object market_info, str order_id):
        pass

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