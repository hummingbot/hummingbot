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

from .constant_spread_pricing_delegate import ConstantSpreadPricingDelegate
from .constant_size_sizing_delegate import ConstantSizeSizingDelegate
from .data_types import (
    MarketInfo,
    OrdersProposal,
    ORDER_PROPOSAL_ACTION_CANCEL_ORDERS,
    ORDER_PROPOSAL_ACTION_CREATE_ORDERS,
    PricingProposal,
    SizingProposal
)
from .order_filter_delegate cimport OrderFilterDelegate
from .order_filter_delegate import OrderFilterDelegate
from .order_pricing_delegate cimport OrderPricingDelegate
from .order_pricing_delegate import OrderPricingDelegate
from .order_sizing_delegate cimport OrderSizingDelegate
from .order_sizing_delegate import OrderSizingDelegate
from .pass_through_filter_delegate import PassThroughFilterDelegate

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
    TRANSACTION_FAILURE_EVENT_TAG = MarketEvent.OrderFailure.value

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

    NO_OP_ORDERS_PROPOSAL = OrdersProposal(0, OrderType.LIMIT, [0], [0], OrderType.LIMIT, [0], [0], [])

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
                 legacy_order_size: float = 1.0,
                 legacy_bid_spread: float = 0.01,
                 legacy_ask_spread: float = 0.01,
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
        # For remembering when to expire orders.
        self._time_to_cancel = {}
        self._in_flight_cancels = {}

        self._logging_options = logging_options
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self._limit_order_min_expiration = limit_order_min_expiration

        if filter_delegate is None:
            filter_delegate = PassThroughFilterDelegate()
        if pricing_delegate is None:
            pricing_delegate = ConstantSpreadPricingDelegate(legacy_bid_spread, legacy_ask_spread)
        if sizing_delegate is None:
            sizing_delegate = ConstantSizeSizingDelegate(legacy_order_size)


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
        maker_orders = []
        for market_info, orders_map in self._tracked_maker_orders.items():
            for limit_order in orders_map.values():
                if limit_order.client_order_id in self._in_flight_cancels:
                    if self._in_flight_cancels.get(limit_order.client_order_id) + self.CANCEL_EXPIRY_DURATION < self._current_timestamp:
                        continue
                maker_orders.append((market_info.market, limit_order))
        return maker_orders

    @property
    def market_info_to_active_orders(self) -> Dict[MarketInfo, List[LimitOrder]]:
        market_info_to_orders = {}
        for market_info in self._market_infos.values():
            maker_orders = []
            for limit_order in self._tracked_maker_orders.get(market_info, {}).values():
                if limit_order.client_order_id in self._in_flight_cancels:
                    if self._in_flight_cancels.get(limit_order.client_order_id) + self.CANCEL_EXPIRY_DURATION < self._current_timestamp:
                        continue
                maker_orders.append(limit_order)

            market_info_to_orders[market_info] = maker_orders
        return market_info_to_orders

    @property
    def active_bids(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return [(market, limit_order) for market, limit_order in self.active_maker_orders if limit_order.is_buy]

    @property
    def active_asks(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return [(market, limit_order) for market, limit_order in self.active_maker_orders if not limit_order.is_buy]

    @property
    def in_flight_cancels(self) -> Dict[str, float]:
        return self._in_flight_cancels

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
                lines.extend(["", "  No active maker orders."])

            # Add warning lines on null balances.
            if maker_base_balance <= 0:
                warning_lines.append(f"  Maker market {maker_base} balance is 0. No ask order is possible.")
            if maker_quote_balance <= 0:
                warning_lines.append(f"  Maker market {maker_quote} balance is 0. No bid order is possible.")

        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    # The following exposed Python functions are meant for unit tests
    # ---------------------------------------------------------------
    def execute_orders_proposal(self, market_info: MarketInfo, orders_proposal: OrdersProposal):
        return self.c_execute_orders_proposal(market_info, orders_proposal)

    def cancel_order(self, market_info: MarketInfo, order_id:str):
        return self.c_cancel_order(market_info, order_id)

    def get_order_price_proposal(self, market_info: MarketInfo) -> PricingProposal:
        active_orders = []
        for limit_order in self._tracked_maker_orders.get(market_info, {}).values():
            if limit_order.client_order_id in self._in_flight_cancels:
                if self._in_flight_cancels[limit_order.client_order_id] + self.CANCEL_EXPIRY_DURATION < self._current_timestamp:
                        continue
            active_orders.append(limit_order)

        return self._pricing_delegate.c_get_order_price_proposal(
            self, market_info, active_orders
        )

    def get_order_size_proposal(self, market_info: MarketInfo, pricing_proposal: PricingProposal) -> SizingProposal:
        active_orders = []
        for limit_order in self._tracked_maker_orders.get(market_info, {}).values():
            if limit_order.client_order_id in self._in_flight_cancels:
                if self._in_flight_cancels[limit_order.client_order_id] + self.CANCEL_EXPIRY_DURATION < self._current_timestamp:
                        continue
            active_orders.append(limit_order)

        return self._sizing_delegate.c_get_order_size_proposal(
            self, market_info, active_orders, pricing_proposal
        )


    def get_orders_proposal_for_market_info(self,
                                            market_info: MarketInfo,
                                            active_orders: List[LimitOrder]) -> OrdersProposal:
        return self.c_get_orders_proposal_for_market_info(market_info, active_orders)
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

        if order_id in self.in_flight_cancels:
            return

        # Track the cancel and tell maker market to cancel the order.
        self._in_flight_cancels[order_id] = self._current_timestamp
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
                self._delegate_lock = True
                orders_proposal = None
                try:
                    orders_proposal = self.c_get_orders_proposal_for_market_info(
                        market_info,
                        market_info_to_active_orders[market_info]
                    )
                except Exception:
                    self.logger().error("Unknown error while generating order proposals.", exc_info=True)
                finally:
                    self._delegate_lock = False
                self.c_execute_orders_proposal(market_info, orders_proposal)

            self.c_check_and_cleanup_shadow_records()
        finally:
            self._last_timestamp = timestamp

    cdef object c_get_orders_proposal_for_market_info(self, object market_info, list active_orders):
        cdef:
            double last_trade_price
            MarketBase maker_market = market_info.market
            int actions = 0
            list cancel_order_ids = []

        # Before doing anything, ask the filter delegate whether to proceed or not.
        if not self._filter_delegate.c_should_proceed_with_processing(self, market_info, active_orders):
            return self.NO_OP_ORDERS_PROPOSAL

        # If there are no active orders, then do the following:
        #  1. Ask the pricing delegate on what are the order prices.
        #  2. Ask the sizing delegate on what are the order sizes.
        #  3. Set the actions to carry out in the orders proposal to include create orders.
        pricing_proposal = self._pricing_delegate.c_get_order_price_proposal(self, market_info, active_orders)
        sizing_proposal = self._sizing_delegate.c_get_order_size_proposal(self,
                                                                          market_info,
                                                                          active_orders,
                                                                          pricing_proposal)
        if sizing_proposal.buy_order_sizes[0] > 0 or sizing_proposal.sell_order_sizes[0] > 0:
            actions |= ORDER_PROPOSAL_ACTION_CREATE_ORDERS

        if maker_market.name not in self.RADAR_RELAY_TYPE_EXCHANGES:
            for active_order in active_orders:
                # If there are active orders, and active order cancellation is needed, then do the following:
                #  1. Check the time to cancel for each order, and see if cancellation should be proposed.
                #  2. Record each order id that needs to be cancelled.
                #  3. Set action to include cancel orders.
                if self._current_timestamp >= self._time_to_cancel[active_order.client_order_id]:
                    cancel_order_ids.append(active_order.client_order_id)

            if len(cancel_order_ids) > 0:
                actions |= ORDER_PROPOSAL_ACTION_CANCEL_ORDERS

        return OrdersProposal(actions,
                              OrderType.LIMIT,
                              pricing_proposal.buy_order_prices,
                              sizing_proposal.buy_order_sizes,
                              OrderType.LIMIT,
                              pricing_proposal.sell_order_prices,
                              sizing_proposal.sell_order_sizes,
                              cancel_order_ids)


    cdef c_did_fill_order(self, object order_filled_event):
        cdef:
            str order_id = order_filled_event.order_id
            object market_info = self._shadow_order_id_to_market_info.get(order_id)
            tuple order_fill_record

        if market_info is not None:
            limit_order_record = self._shadow_tracked_maker_orders[market_info][order_id]
            order_fill_record = (limit_order_record, order_filled_event)

            if order_filled_event.trade_type is TradeType.BUY:
                if self._logging_options & self.OPTION_LOG_MAKER_ORDER_FILLED:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_info.symbol}) Maker buy order of "
                        f"{order_filled_event.amount} {market_info.base_currency} filled."
                    )
            else:
                if self._logging_options & self.OPTION_LOG_MAKER_ORDER_FILLED:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_info.symbol}) Maker sell order of "
                        f"{order_filled_event.amount} {market_info.base_currency} filled."
                    )

    cdef c_did_fail_order(self, object order_failed_event):
        cdef:
            str order_id = order_failed_event.order_id
            object market_info= self._order_id_to_market_info.get(order_id)

        if market_info is None:
            return
        self.c_stop_tracking_order(market_info, order_id)

    cdef c_did_cancel_order(self, object cancelled_event):
        cdef:
            str order_id = cancelled_event.order_id
            object market_info = self._order_id_to_market_info.get(order_id)
        self.c_stop_tracking_order(market_info, order_id)

    cdef c_did_complete_buy_order(self, object order_completed_event):
        cdef:
            str order_id = order_completed_event.order_id
            object market_info = self._order_id_to_market_info.get(order_id)
            LimitOrder limit_order_record

        if market_info is not None:
            limit_order_record = self._tracked_maker_orders[market_info][order_id]
            self.log_with_clock(
                logging.INFO,
                f"({market_info.symbol}) Maker buy order {order_id} "
                f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
            )
        self.c_stop_tracking_order(market_info, order_id)

    cdef c_did_complete_sell_order(self, object order_completed_event):
        cdef:
            str order_id = order_completed_event.order_id
            object market_info = self._order_id_to_market_info.get(order_id)
            LimitOrder limit_order_record

        if market_info is not None:
            limit_order_record = self._tracked_maker_orders[market_info][order_id]
            self.log_with_clock(
                logging.INFO,
                f"({market_info.symbol}) Maker sell order {order_id} "
                f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
            )
        self.c_stop_tracking_order(market_info, order_id)

    cdef c_start_tracking_order(self, object market_info, str order_id, bint is_buy, object price, object quantity):
        if market_info not in self._tracked_maker_orders:
            self._tracked_maker_orders[market_info] = {}
        if market_info not in self._shadow_tracked_maker_orders:
            self._shadow_tracked_maker_orders[market_info] = {}

        cdef:
            LimitOrder limit_order = LimitOrder(order_id,
                                                market_info.symbol,
                                                is_buy,
                                                market_info.base_currency,
                                                market_info.quote_currency,
                                                float(price),
                                                float(quantity))
        self._tracked_maker_orders[market_info][order_id] = limit_order
        self._shadow_tracked_maker_orders[market_info][order_id] = limit_order
        self._order_id_to_market_info[order_id] = market_info
        self._shadow_order_id_to_market_info[order_id] = market_info

    cdef c_stop_tracking_order(self, object market_info, str order_id):
        if market_info in self._tracked_maker_orders and order_id in self._tracked_maker_orders[market_info]:
            del self._tracked_maker_orders[market_info][order_id]
            if len(self._tracked_maker_orders[market_info]) < 1:
                del self._tracked_maker_orders[market_info]
        if order_id in self._order_id_to_market_info:
            del self._order_id_to_market_info[order_id]
        self._shadow_gc_requests.append((
            self._current_timestamp + self.SHADOW_MAKER_ORDER_KEEP_ALIVE_DURATION,
            market_info,
            order_id
        ))

    cdef c_check_and_cleanup_shadow_records(self):
        cdef:
            double current_timestamp = self._current_timestamp

        while len(self._shadow_gc_requests) > 0 and self._shadow_gc_requests[0][0] < current_timestamp:
            _, market_info, order_id = self._shadow_gc_requests.popleft()
            if (market_info in self._shadow_tracked_maker_orders and
                    order_id in self._shadow_tracked_maker_orders[market_info]):
                del self._shadow_tracked_maker_orders[market_info][order_id]
                if len(self._shadow_tracked_maker_orders[market_info]) < 1:
                    del self._shadow_tracked_maker_orders[market_info]
            if order_id in self._shadow_order_id_to_market_info:
                del self._shadow_order_id_to_market_info[order_id]

    cdef c_execute_orders_proposal(self, object market_info, object orders_proposal):
        cdef:
            int64_t actions = orders_proposal.actions
            MarketBase market = market_info.market
            str symbol = market_info.symbol
            double expiration_seconds = (self._cancel_order_wait_time
                                         if market.name in self.RADAR_RELAY_TYPE_EXCHANGES
                                         else NaN)
            str bid_order_id

        # Cancel orders.
        if actions & ORDER_PROPOSAL_ACTION_CANCEL_ORDERS:
            for order_id in orders_proposal.cancel_order_ids:
                self.log_with_clock(
                    logging.INFO,
                    f"({market_info.symbol}) Cancelling the limit order {order_id}."
                )
                self.c_cancel_order(market_info, order_id)

        # Create orders.
        if actions & ORDER_PROPOSAL_ACTION_CREATE_ORDERS:
            if orders_proposal.buy_order_sizes[0] > 0:
                if orders_proposal.buy_order_type is OrderType.LIMIT and orders_proposal.buy_order_prices[0] > 0:
                    if self._logging_options & self.OPTION_LOG_CREATE_ORDER:
                        self.log_with_clock(
                            logging.INFO,
                            f"({market_info.symbol}) Creating limit bid orders for "
                            f"  Bids (Size,Price) to be placed at: {[str(size) + ' ' + market_info.base_currency + ' @ ' + ' ' + str(price) + ' ' + market_info.quote_currency for size,price in zip(orders_proposal.buy_order_sizes, orders_proposal.buy_order_prices)]}"
                        )

                    for idx in range(len(orders_proposal.buy_order_sizes)):
                        bid_order_id = self.c_buy_with_specific_market(
                            market,
                            symbol,
                            orders_proposal.buy_order_sizes[idx],
                            orders_proposal.buy_order_prices[idx],
                            order_type=OrderType.LIMIT,
                            expiration_seconds=expiration_seconds
                        )
                        self.c_start_tracking_order(
                            market_info,
                            bid_order_id,
                            True,
                            orders_proposal.buy_order_prices[idx],
                            orders_proposal.buy_order_sizes[idx]
                        )
                        self._time_to_cancel[bid_order_id] = self._current_timestamp + self._cancel_order_wait_time
                elif orders_proposal.buy_order_type is OrderType.MARKET:
                    raise RuntimeError("Market buy order in orders proposal is not supported yet.")

            if orders_proposal.sell_order_sizes[0] > 0:
                if orders_proposal.sell_order_type is OrderType.LIMIT and orders_proposal.sell_order_prices[0] > 0:
                    if self._logging_options & self.OPTION_LOG_CREATE_ORDER:
                        self.log_with_clock(
                            logging.INFO,
                            f"({market_info.symbol}) Creating limit ask order for "
                            f"  Asks (Size,Price) to be placed at: {[str(size) + ' ' + market_info.base_currency + ' @ ' + ' ' + str(price) + ' ' + market_info.quote_currency for size,price in zip(orders_proposal.sell_order_sizes, orders_proposal.sell_order_prices)]}"
                        )

                    for idx in range(len(orders_proposal.sell_order_sizes)):
                        ask_order_id = self.c_sell_with_specific_market(
                            market,
                            symbol,
                            orders_proposal.sell_order_sizes[idx],
                            orders_proposal.sell_order_prices[idx],
                            order_type=OrderType.LIMIT,
                            expiration_seconds=expiration_seconds
                        )
                        self.c_start_tracking_order(
                            market_info,
                            ask_order_id,
                            False,
                            orders_proposal.sell_order_prices[idx],
                            orders_proposal.sell_order_sizes[idx]
                        )
                        self._time_to_cancel[ask_order_id] = self._current_timestamp + self._cancel_order_wait_time
                elif orders_proposal.sell_order_type is OrderType.MARKET:
                    raise RuntimeError("Market sell order in orders proposal is not supported yet.")
