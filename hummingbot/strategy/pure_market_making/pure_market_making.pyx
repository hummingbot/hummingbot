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
from .pure_market_pair import PureMarketPair
from hummingbot.strategy.strategy_base import StrategyBase

NaN = float("nan")
s_decimal_zero = Decimal(0)
s_logger = None


cdef class BasePureMakingStrategyEventListener(EventListener):
    cdef:
        PureMarketMakingStrategy _owner

    def __init__(self, PureMarketMakingStrategy owner):
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


cdef class PureMarketMakingStrategy(StrategyBase):
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

    def __init__(self, market_pairs: List[PureMarketPair],
                 order_size: float = 1.0,
                 bid_place_threshold: float = 0.01,
                 ask_place_threshold: float = 0.01,
                 cancel_order_wait_time: float = 60,
                 logging_options: int = OPTION_LOG_ALL,
                 limit_order_min_expiration: float = 130.0,
                 status_report_interval: float = 900):

        if len(market_pairs) < 0:
            raise ValueError(f"market_pairs must not be empty.")

        super().__init__()
        self._market_pairs = {
            (market_pair.maker_market, market_pair.maker_symbol): market_pair
            for market_pair in market_pairs
        }
        self._maker_markets = set([market_pair.maker_market for market_pair in market_pairs])
        self._all_markets_ready = False
        self._markets = self._maker_markets
        self._bid_place_threshold = bid_place_threshold
        self._ask_place_threshold = ask_place_threshold
        self._order_size = order_size
        self._cancel_order_wait_time = cancel_order_wait_time
        # Add radar relay type exchanges where you can expire orders instead of cancelling them
        self._radar_relay_type_exchanges = {'radar_relay', 'bamboo_relay'}
        # For tracking limit orders
        self._tracked_maker_orders = {}
        # Preserving a copy of limit orders for safety for sometime
        self._shadow_tracked_maker_orders = {}
        self._order_id_to_market_pair = {}
        self._shadow_order_id_to_market_pair = {}
        # For cleaning up limit orders
        self._shadow_gc_requests = deque()

        self._time_to_cancel = {}
        self._order_fill_buy_events = {}
        self._order_fill_sell_events = {}
        self._in_flight_cancels = OrderedDict()
        self._buy_order_completed_listener = BuyOrderCompletedListener(self)
        self._sell_order_completed_listener = SellOrderCompletedListener(self)
        self._order_filled_listener = OrderFilledListener(self)
        self._order_failed_listener = OrderFailedListener(self)
        self._order_cancelled_listener = OrderCancelledListener(self)
        self._order_expired_listener = OrderExpiredListener(self)
        self._logging_options = <int64_t>logging_options
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self._limit_order_min_expiration = limit_order_min_expiration

        cdef:
            MarketBase typed_market

        for market in self._maker_markets:
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
            (market_pair.maker_market, limit_order)
            for market_pair, orders_map in self._tracked_maker_orders.items()
            for limit_order in orders_map.values()
        ]

    @property
    def cached_maker_orders(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return [
            (market_pair.maker_market, limit_order)
            for market_pair, orders_map in self._shadow_tracked_maker_orders.items()
            for limit_order in orders_map.values()
        ]

    @property
    def active_bids(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return [(market, limit_order) for market, limit_order in self.active_maker_orders if limit_order.is_buy]

    @property
    def active_asks(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return [(market, limit_order) for market, limit_order in self.active_maker_orders if not limit_order.is_buy]

    @property
    def logging_options(self) -> int:
        return self._logging_options

    @property
    def bid_place_threshold(self) -> float:
        return self._bid_place_threshold

    @property
    def ask_place_threshold(self) -> float:
        return self._ask_place_threshold

    @property
    def order_size(self) -> float:
        return self._order_size

    @logging_options.setter
    def logging_options(self, int64_t logging_options):
        self._logging_options = logging_options

    def log_with_clock(self, log_level: int, msg: str, **kwargs):
        clock_timestamp = pd.Timestamp(self._current_timestamp, unit="s", tz="UTC")
        self.logger().log(log_level, f"{msg} [clock={str(clock_timestamp)}]", **kwargs)

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

        for market_pair in self._market_pairs.values():
            # Get some basic info about the market pair.
            maker_market = market_pair.maker_market
            maker_symbol = market_pair.maker_symbol
            maker_name = maker_market.name
            maker_base = market_pair.maker_base_currency
            maker_quote = market_pair.maker_quote_currency
            maker_order_book = maker_market.c_get_order_book(maker_symbol)
            maker_base_balance = maker_market.c_get_balance(maker_base)
            maker_quote_balance = maker_market.c_get_balance(maker_quote)
            bid_price = maker_order_book.get_price(False)
            ask_price = maker_order_book.get_price(True)

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

            lines.extend([
                f"{market_pair.maker_symbol}:",
                f"  {maker_symbol} bid/ask: {bid_price}/{ask_price}",
                f"  Bid to be placed at: {bid_price * (1-self.bid_place_threshold)}",
                f"  Ask to be placed at: {ask_price * (1+self.ask_place_threshold)}",
                f"  {maker_base}/{maker_quote} balance: "
                    f"{maker_base_balance}/{maker_quote_balance}"
            ])

            # See if there're any open orders.
            if market_pair in self._tracked_maker_orders and len(self._tracked_maker_orders[market_pair]) > 0:
                limit_orders = list(self._tracked_maker_orders[market_pair].values())
                df = LimitOrder.to_pandas(limit_orders)
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

    def check_if_sufficient_balance(self, market_pair: PureMarketPair) -> bool:
        return self.c_check_if_sufficient_balance(market_pair)

    def create_new_orders(self, market_pair: PureMarketPair):
        return self.c_create_new_orders(market_pair)

    def cancel_order(self, market_pair: PureMarketPair,order_id:str):
        return self.c_cancel_order(market_pair,order_id)

    # ---------------------------------------------------------------

    cdef c_buy_with_specific_market(self, MarketBase market, str symbol, double amount,
                                    double price,
                                    object order_type = OrderType.LIMIT,
                                    double expiration_seconds = NaN):
        cdef:
            dict kwargs = {}

        kwargs["expiration_ts"] = self._current_timestamp + max(self._limit_order_min_expiration, expiration_seconds)

        if market not in self._markets:
            raise ValueError(f"market object for buy order is not in the whitelisted markets set.")
        return market.c_buy(symbol, amount,
                            order_type=order_type, price=price, kwargs=kwargs)

    cdef c_sell_with_specific_market(self, MarketBase market, str symbol, double amount,
                                     double price,
                                     object order_type = OrderType.LIMIT,
                                     double expiration_seconds = NaN):
        cdef:
            dict kwargs = {}

        kwargs["expiration_ts"] = self._current_timestamp + max(self._limit_order_min_expiration, expiration_seconds)

        if market not in self._markets:
            raise ValueError(f"market object for sell order is not in the whitelisted markets set.")
        return market.c_sell(symbol, amount,
                             order_type=order_type, price=price, kwargs=kwargs)

    cdef c_cancel_order(self, object market_pair, str order_id):
        cdef:
            MarketBase maker_market = market_pair.maker_market
            list keys_to_delete = []

        # Maintain the cancel expiry time invariant
        for k, cancel_timestamp in self._in_flight_cancels.items():
            if cancel_timestamp < self._current_timestamp - self.CANCEL_EXPIRY_DURATION:
                keys_to_delete.append(k)
        for k in keys_to_delete:
            del self._in_flight_cancels[k]

        # Track the cancel and tell maker market to cancel the order.
        self._in_flight_cancels[order_id] = self._current_timestamp
        maker_market.c_cancel(market_pair.maker_symbol, order_id)

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

            market_pair_to_active_orders = defaultdict(list)

            for maker_market, limit_order in active_maker_orders:
                market_pair = self._market_pairs.get((maker_market, limit_order.symbol))
                if market_pair is None:
                    self.log_with_clock(logging.WARNING,
                                        f"The maker order for the symbol '{limit_order.symbol}' "
                                        f"does not correspond to any whitelisted market pairs. Skipping.")
                    continue

                if (self._in_flight_cancels.get(limit_order.client_order_id, 0) <
                        self._current_timestamp - self.CANCEL_EXPIRY_DURATION):
                    market_pair_to_active_orders[market_pair].append(limit_order)

            for market_pair in self._market_pairs.values():
                self.c_process_market_pair(market_pair, market_pair_to_active_orders[market_pair])

            self.c_check_and_cleanup_shadow_records()
        finally:
            self._last_timestamp = timestamp

    cdef c_process_market_pair(self, object market_pair, list active_orders):
        cdef:
            double last_trade_price
            MarketBase maker_market = market_pair.maker_market
            OrderBook maker_order_book
            bint is_buy
            double current_timestamp = self._current_timestamp
            str maker_name = maker_market.name

        global s_decimal_zero

        # If there are no active orders
        if not len(active_orders):
            # Set cancellation time to be current timestamp + cancel order wait time
            self._time_to_cancel[market_pair] = current_timestamp + self._cancel_order_wait_time

            # See if I still have enough balance on my wallet to place the bid and ask orders
            # If not don't place orders
            if not self.c_check_if_sufficient_balance(market_pair):
                return

            # Create new bid and ask orders
            self.c_create_new_orders(market_pair)

        #If there are active orders check if the current timestamp exceeds time to cancel
        else:
            #No need to cancel if its radar relay type exchange, use expiration instead
            if maker_name in self._radar_relay_type_exchanges:
                return

            if current_timestamp >= self._time_to_cancel[market_pair]:

                 for active_order in active_orders:
                    #Cancel active orders
                    self.c_cancel_order(market_pair, active_order.client_order_id)


    cdef c_did_fill_order(self, object order_filled_event):
        cdef:
            str order_id = order_filled_event.order_id
            object market_pair = self._shadow_order_id_to_market_pair.get(order_id)
            tuple order_fill_record

        if market_pair is not None:
            limit_order_record = self._shadow_tracked_maker_orders[market_pair][order_id]
            order_fill_record = (limit_order_record, order_filled_event)

            if order_filled_event.trade_type is TradeType.BUY:
                if market_pair not in self._order_fill_buy_events:
                    self._order_fill_buy_events[market_pair] = [order_fill_record]
                else:
                    self._order_fill_buy_events[market_pair].append(order_fill_record)

                if self._logging_options & self.OPTION_LOG_MAKER_ORDER_FILLED:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_pair.maker_symbol}) Maker buy order of "
                        f"{order_filled_event.amount} {market_pair.maker_base_currency} filled."
                    )
            else:
                if market_pair not in self._order_fill_sell_events:
                    self._order_fill_sell_events[market_pair] = [order_fill_record]
                else:
                    self._order_fill_sell_events[market_pair].append(order_fill_record)

                if self._logging_options & self.OPTION_LOG_MAKER_ORDER_FILLED:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_pair.maker_symbol}) Maker sell order of "
                        f"{order_filled_event.amount} {market_pair.maker_base_currency} filled."
                    )

    cdef c_did_fail_order(self, object order_failed_event):
        cdef:
            str order_id = order_failed_event.order_id
            object market_pair = self._order_id_to_market_pair.get(order_id)

        if market_pair is None:
            return
        self.c_stop_tracking_order(market_pair, order_id)

    cdef c_did_cancel_order(self, object cancelled_event):
        cdef:
            str order_id = cancelled_event.order_id
            object market_pair = self._order_id_to_market_pair.get(order_id)

        self.c_stop_tracking_order(market_pair, order_id)

    cdef c_did_complete_buy_order(self, object order_completed_event):
        cdef:
            str order_id = order_completed_event.order_id
            object market_pair = self._order_id_to_market_pair.get(order_id)
            LimitOrder limit_order_record

        if market_pair is not None:
            limit_order_record = self._tracked_maker_orders[market_pair][order_id]
            self.log_with_clock(
                logging.INFO,
                f"({market_pair.maker_symbol}) Maker buy order {order_id} "
                f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
            )

    cdef c_did_complete_sell_order(self, object order_completed_event):
        cdef:
            str order_id = order_completed_event.order_id
            object market_pair = self._order_id_to_market_pair.get(order_id)
            LimitOrder limit_order_record

        if market_pair is not None:
            limit_order_record = self._tracked_maker_orders[market_pair][order_id]
            self.log_with_clock(
                logging.INFO,
                f"({market_pair.maker_symbol}) Maker sell order {order_id} "
                f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
            )

    cdef c_start_tracking_order(self, object market_pair, str order_id, bint is_buy, object price, object quantity):
        if market_pair not in self._tracked_maker_orders:
            self._tracked_maker_orders[market_pair] = {}
        if market_pair not in self._shadow_tracked_maker_orders:
            self._shadow_tracked_maker_orders[market_pair] = {}

        cdef:
            LimitOrder limit_order = LimitOrder(order_id,
                                                market_pair.maker_symbol,
                                                is_buy,
                                                market_pair.maker_base_currency,
                                                market_pair.maker_quote_currency,
                                                float(price),
                                                float(quantity))
        self._tracked_maker_orders[market_pair][order_id] = limit_order
        self._shadow_tracked_maker_orders[market_pair][order_id] = limit_order
        self._order_id_to_market_pair[order_id] = market_pair
        self._shadow_order_id_to_market_pair[order_id] = market_pair

    cdef c_stop_tracking_order(self, object market_pair, str order_id):
        if market_pair in self._tracked_maker_orders and order_id in self._tracked_maker_orders[market_pair]:
            del self._tracked_maker_orders[market_pair][order_id]
            if len(self._tracked_maker_orders[market_pair]) < 1:
                del self._tracked_maker_orders[market_pair]
        if order_id in self._order_id_to_market_pair:
            del self._order_id_to_market_pair[order_id]
        self._shadow_gc_requests.append((
            self._current_timestamp + self.SHADOW_MAKER_ORDER_KEEP_ALIVE_DURATION,
            market_pair,
            order_id
        ))

    cdef c_check_and_cleanup_shadow_records(self):
        cdef:
            double current_timestamp = self._current_timestamp

        while len(self._shadow_gc_requests) > 0 and self._shadow_gc_requests[0][0] < current_timestamp:
            _, market_pair, order_id = self._shadow_gc_requests.popleft()
            if (market_pair in self._shadow_tracked_maker_orders and
                    order_id in self._shadow_tracked_maker_orders[market_pair]):
                del self._shadow_tracked_maker_orders[market_pair][order_id]
                if len(self._shadow_tracked_maker_orders[market_pair]) < 1:
                    del self._shadow_tracked_maker_orders[market_pair]
            if order_id in self._shadow_order_id_to_market_pair:
                del self._shadow_order_id_to_market_pair[order_id]

    cdef bint c_check_if_sufficient_balance(self, object market_pair):
        cdef:
            MarketBase maker_market = market_pair.maker_market
            double quote_asset_amount = maker_market.c_get_balance(market_pair.maker_quote_currency)
            double base_asset_amount = maker_market.c_get_balance(market_pair.maker_base_currency)
            top_bid_price = maker_market.c_get_price(market_pair.maker_symbol, False)

        if base_asset_amount < self.order_size:
            if self._logging_options:
                self.log_with_clock(
                    logging.INFO,
                    f"({market_pair.maker_base_currency}) balance of ({base_asset_amount:.8g}) "
                    f"is less than the required size of: ({self.order_size:.8g}). "
                    f"Running again"
                )
            return False

        if quote_asset_amount < (top_bid_price * self.order_size):
            if self._logging_options:
                self.log_with_clock(
                    logging.INFO,
                    f"({market_pair.maker_quote_currency}) balance of  ({quote_asset_amount:.8g}) "
                    f"is now less than the required to place an ask order of size: ({self.order_size:.8g}). "
                    f"Running again"
                )
            return False

        return True

    cdef c_create_new_orders(self, object market_pair):
        cdef:
            MarketBase maker_market = market_pair.maker_market
            OrderBook maker_order_book = maker_market.c_get_order_book(market_pair.maker_symbol)
            double top_bid_price = maker_market.c_get_price(market_pair.maker_symbol, False)
            double top_ask_price = maker_market.c_get_price(market_pair.maker_symbol, True)
            str maker_name = maker_market.name
            object price_quant = maker_market.get_order_price_quantum(
                market_pair.maker_symbol,
                top_bid_price
            )
            double mid_price = (top_ask_price + top_bid_price) / 2
            double place_bid_price = mid_price * (1 - self.bid_place_threshold)
            double place_ask_price = mid_price * (1 + self.ask_place_threshold)

        if maker_name in self._radar_relay_type_exchanges:
            expiration_seconds = self._cancel_order_wait_time
        else:
            expiration_seconds = NaN

        if self._logging_options & self.OPTION_LOG_CREATE_ORDER:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_pair.maker_symbol}) Creating limit bid order for "
                        f"{self.order_size} {market_pair.maker_base_currency} at "
                        f"{place_bid_price} {market_pair.maker_quote_currency}."
                    )

        bid_order_id = self.c_buy_with_specific_market(
                    maker_market,
                    market_pair.maker_symbol,
                    self.order_size,
                    place_bid_price,
                    OrderType.LIMIT,
                    expiration_seconds
                )

        self.c_start_tracking_order(
            market_pair,
            bid_order_id,
            True,
            place_bid_price,
            self.order_size
        )

        if self._logging_options & self.OPTION_LOG_CREATE_ORDER:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_pair.maker_symbol}) Creating limit ask order for "
                        f"{self.order_size} {market_pair.maker_base_currency} at "
                        f"{place_ask_price} {market_pair.maker_quote_currency}."
                    )

        ask_order_id = self.c_sell_with_specific_market(
                    maker_market,
                    market_pair.maker_symbol,
                    self.order_size,
                    place_ask_price,
                    OrderType.LIMIT,
                    expiration_seconds
                )

        self.c_start_tracking_order(
                    market_pair,
                    ask_order_id,
                    False,
                    place_ask_price,
                    self.order_size
                )