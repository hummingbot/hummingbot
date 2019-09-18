from decimal import Decimal
import logging
from typing import (
    List,
    Tuple,
    Optional,
    Dict
)

from hummingbot.core.clock cimport Clock
from hummingbot.core.event.events import TradeType
from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.market.market_base cimport MarketBase
from hummingbot.market.market_base import (
    MarketBase,
    OrderType
)
from hummingbot.strategy.market_symbol_pair import MarketSymbolPair
from hummingbot.strategy.strategy_base import StrategyBase

from .pass_through_filter_delegate import PassThroughFilterDelegate
from .data_types import (
    OrdersProposal,
    ORDER_PROPOSAL_ACTION_CANCEL_ORDERS,
    ORDER_PROPOSAL_ACTION_CREATE_ORDERS,
    PricingProposal,
    SizingProposal
)
from .pure_market_making_order_tracker import PureMarketMakingOrderTracker
from .order_filter_delegate cimport OrderFilterDelegate
from .order_filter_delegate import OrderFilterDelegate
from .order_pricing_delegate cimport OrderPricingDelegate
from .order_pricing_delegate import OrderPricingDelegate
from .order_sizing_delegate cimport OrderSizingDelegate
from .order_sizing_delegate import OrderSizingDelegate

NaN = float("nan")
s_decimal_zero = Decimal(0)
s_logger = None


cdef class PureMarketMakingStrategyV2(StrategyBase):
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

    NO_OP_ORDERS_PROPOSAL = OrdersProposal(0,
                                           OrderType.LIMIT, [s_decimal_zero], [s_decimal_zero],
                                           OrderType.LIMIT, [s_decimal_zero], [s_decimal_zero],
                                           [])

    # These are exchanges where you're expected to expire orders instead of actively cancelling them.
    RADAR_RELAY_TYPE_EXCHANGES = {"radar_relay", "bamboo_relay"}

    SINGLE_ORDER_SIZING_DELEGATES = {"constant_size", "inventory_skew_single_size"}

    @classmethod
    def logger(cls):
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 market_infos: List[MarketSymbolPair],
                 pricing_delegate: OrderPricingDelegate,
                 sizing_delegate: OrderSizingDelegate,
                 cancel_order_wait_time: float = 60,
                 filled_order_replenish_wait_time: float = 10,
                 enable_order_filled_stop_cancellation: bool = False,
                 logging_options: int = OPTION_LOG_ALL,
                 limit_order_min_expiration: float = 130.0,
                 status_report_interval: float = 900):

        if len(market_infos) < 1:
            raise ValueError(f"market_infos must not be empty.")

        super().__init__()
        self._sb_order_tracker = PureMarketMakingOrderTracker()
        self._market_infos = {
            (market_info.market, market_info.trading_pair): market_info
            for market_info in market_infos
        }
        self._all_markets_ready = False
        self._cancel_order_wait_time = cancel_order_wait_time
        self._filled_order_replenish_wait_time = filled_order_replenish_wait_time

        self._time_to_cancel = {}

        self._logging_options = logging_options
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval

        # Create a filter delegate which will create orders after the current timestamp
        self._filter_delegate = PassThroughFilterDelegate(self._current_timestamp)
        self._pricing_delegate = pricing_delegate
        self._sizing_delegate = sizing_delegate
        self._enable_order_filled_stop_cancellation = enable_order_filled_stop_cancellation

        self.limit_order_min_expiration = limit_order_min_expiration

        cdef:
            set all_markets = set([market_info.market for market_info in market_infos])

        self.c_add_markets(list(all_markets))

    @property
    def active_maker_orders(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return self._sb_order_tracker.active_maker_orders

    @property
    def market_info_to_active_orders(self) -> Dict[MarketSymbolPair, List[LimitOrder]]:
        return self._sb_order_tracker.market_pair_to_active_orders

    @property
    def active_bids(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return self._sb_order_tracker.active_bids

    @property
    def active_asks(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return self._sb_order_tracker.active_asks

    @property
    def in_flight_cancels(self) -> Dict[str, float]:
        return self._sb_order_tracker.in_flight_cancels

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

    @property
    def sizing_delegate_name(self) -> str:
        return self._sizing_delegate.name

    @property
    def order_tracker(self):
        return self._sb_order_tracker

    def format_status(self) -> str:
        cdef:
            list lines = []
            list warning_lines = []
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

    # The following exposed Python functions are meant for unit tests
    # ---------------------------------------------------------------
    def execute_orders_proposal(self, market_info: MarketSymbolPair, orders_proposal: OrdersProposal):
        return self.c_execute_orders_proposal(market_info, orders_proposal)

    def cancel_order(self, market_info: MarketSymbolPair, order_id: str):
        return self.c_cancel_order(market_info, order_id)

    def get_order_price_proposal(self, market_info: MarketSymbolPair) -> PricingProposal:
        active_orders = []
        for limit_order in self._sb_order_tracker.c_get_maker_orders().get(market_info, {}).values():
            if self._sb_order_tracker.c_has_in_flight_cancel(limit_order.client_order_id):
                continue
            active_orders.append(limit_order)

        return self._pricing_delegate.c_get_order_price_proposal(
            self, market_info, active_orders
        )

    def get_order_size_proposal(self, market_info: MarketSymbolPair, pricing_proposal: PricingProposal) -> SizingProposal:
        active_orders = []
        for limit_order in self._sb_order_tracker.c_get_maker_orders().get(market_info, {}).values():
            if self._sb_order_tracker.c_has_in_flight_cancel(limit_order.client_order_id):
                continue
            active_orders.append(limit_order)

        return self._sizing_delegate.c_get_order_size_proposal(
            self, market_info, active_orders, pricing_proposal
        )

    def get_orders_proposal_for_market_info(self,
                                            market_info: MarketSymbolPair,
                                            active_orders: List[LimitOrder]) -> OrdersProposal:
        return self.c_get_orders_proposal_for_market_info(market_info, active_orders)
    # ---------------------------------------------------------------

    cdef c_start(self, Clock clock, double timestamp):
        StrategyBase.c_start(self, clock, timestamp)
        self._last_timestamp = timestamp
        self.filter_delegate.order_placing_timestamp = timestamp

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
                self._sb_delegate_lock = True
                orders_proposal = None
                try:
                    orders_proposal = self.c_get_orders_proposal_for_market_info(
                        market_info,
                        market_info_to_active_orders.get(market_info, [])
                    )
                except Exception:
                    self.logger().error("Unknown error while generating order proposals.", exc_info=True)
                finally:
                    self._sb_delegate_lock = False
                filtered_proposal = self._filter_delegate.c_filter_orders_proposal(self,
                                                                                   market_info,
                                                                                   orders_proposal)
                self.c_execute_orders_proposal(market_info, filtered_proposal)
        finally:
            self._last_timestamp = timestamp

    cdef object c_get_orders_proposal_for_market_info(self, object market_info, list active_orders):
        cdef:
            double last_trade_price
            int actions = 0
            list cancel_order_ids = []

        # Before doing anything, ask the filter delegate whether to proceed or not.
        if not self._filter_delegate.c_should_proceed_with_processing(self, market_info, active_orders):
            return self.NO_OP_ORDERS_PROPOSAL

        # If there are no active orders, then do the following:
        #  1. Ask the pricing delegate on what are the order prices.
        #  2. Ask the sizing delegate on what are the order sizes.
        #  3. Set the actions to carry out in the orders proposal to include create orders.

        pricing_proposal = self._pricing_delegate.c_get_order_price_proposal(self,
                                                                             market_info,
                                                                             active_orders)

        sizing_proposal = self._sizing_delegate.c_get_order_size_proposal(self,
                                                                          market_info,
                                                                          active_orders,
                                                                          pricing_proposal)
        if sizing_proposal.buy_order_sizes[0] > 0 or sizing_proposal.sell_order_sizes[0] > 0:
            actions |= ORDER_PROPOSAL_ACTION_CREATE_ORDERS

        if ((market_info.market.name not in self.RADAR_RELAY_TYPE_EXCHANGES) or
                (market_info.market.display_name == "bamboo_relay" and market_info.market.use_coordinator)):
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
            object market_info = self._sb_order_tracker.c_get_shadow_market_pair_from_order_id(order_id)
            tuple order_fill_record

        if market_info is not None:
            limit_order_record = self._sb_order_tracker.c_get_shadow_limit_order(order_id)
            order_fill_record = (limit_order_record, order_filled_event)

            if order_filled_event.trade_type is TradeType.BUY:
                if self._logging_options & self.OPTION_LOG_MAKER_ORDER_FILLED:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_info.trading_pair}) Maker buy order of "
                        f"{order_filled_event.amount} {market_info.base_asset} filled."
                    )
            else:
                if self._logging_options & self.OPTION_LOG_MAKER_ORDER_FILLED:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_info.trading_pair}) Maker sell order of "
                        f"{order_filled_event.amount} {market_info.base_asset} filled."
                    )

    cdef c_did_complete_buy_order(self, object order_completed_event):
        cdef:
            str order_id = order_completed_event.order_id
            object market_info = self._sb_order_tracker.c_get_market_pair_from_order_id(order_id)
            LimitOrder limit_order_record

        # Replenish Delay and order filled stop cancellation are only for single order mode
        # (identified using name of the delegate)
        if self.sizing_delegate_name in self.SINGLE_ORDER_SIZING_DELEGATES:
            # Set the replenish time as current_timestamp + order replenish time
            replenish_time_stamp = self._current_timestamp + self._filled_order_replenish_wait_time

            # if filled order is buy, adjust the cancel time for sell order
            # For syncing buy and sell orders during order completed events
            for _, ask_order in self.active_asks:
                other_order_id = ask_order.client_order_id
                if other_order_id in self._time_to_cancel:

                    # If you want to stop cancelling orders remove it from the cancel list
                    if self._enable_order_filled_stop_cancellation:
                        del self._time_to_cancel[other_order_id]
                    else:
                        # cancel time is minimum of current cancel time and replenish time to sync up both
                        self._time_to_cancel[other_order_id] = min(self._time_to_cancel[other_order_id], replenish_time_stamp)

                # Stop tracking the order
                if self._enable_order_filled_stop_cancellation:
                    self._sb_order_tracker.c_stop_tracking_limit_order(market_info, other_order_id)

            self.filter_delegate.order_placing_timestamp = replenish_time_stamp

        if market_info is not None:
            limit_order_record = self._sb_order_tracker.c_get_limit_order(market_info, order_id)
            self.log_with_clock(
                logging.INFO,
                f"({market_info.trading_pair}) Maker buy order {order_id} "
                f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
            )

    cdef c_did_complete_sell_order(self, object order_completed_event):
        cdef:
            str order_id = order_completed_event.order_id
            object market_info = self._sb_order_tracker.c_get_market_pair_from_order_id(order_id)
            LimitOrder limit_order_record

        # Replenish Delay and order filled stop cancellation are only for single order mode
        # (identified using name of the delegate)
        if self.sizing_delegate_name in self.SINGLE_ORDER_SIZING_DELEGATES:
            # Set the replenish time as current_timestamp + order replenish time
            replenish_time_stamp = self._current_timestamp + self._filled_order_replenish_wait_time

            # if filled order is sell, adjust the cancel time for buy order
            # For syncing buy and sell orders during order completed events
            for _, bid_order in self.active_bids:
                other_order_id = bid_order.client_order_id
                if other_order_id in self._time_to_cancel:

                    # If you want to stop cancelling orders remove it from the cancel list
                    if self._enable_order_filled_stop_cancellation:
                        del self._time_to_cancel[other_order_id]
                    else:
                        # cancel time is minimum of current cancel time and replenish time to sync up both
                        self._time_to_cancel[other_order_id] = min(self._time_to_cancel[other_order_id], replenish_time_stamp)

                # Stop tracking the order
                if self._enable_order_filled_stop_cancellation:
                    self._sb_order_tracker.c_stop_tracking_limit_order(market_info, other_order_id)

            self.filter_delegate.order_placing_timestamp = replenish_time_stamp

        if market_info is not None:
            limit_order_record = self._sb_order_tracker.c_get_limit_order(market_info, order_id)
            self.log_with_clock(
                logging.INFO,
                f"({market_info.trading_pair}) Maker sell order {order_id} "
                f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
            )

    cdef c_execute_orders_proposal(self, object market_info, object orders_proposal):
        cdef:
            int64_t actions = orders_proposal.actions
            double expiration_seconds = (self._cancel_order_wait_time
                                         if ((market_info.market.name in self.RADAR_RELAY_TYPE_EXCHANGES) or
                                             (market_info.market.name == "bamboo_relay" and not market_info.market.use_coordinator))
                                         else NaN)
            str bid_order_id, ask_order_id

        # Cancel orders.
        if actions & ORDER_PROPOSAL_ACTION_CANCEL_ORDERS:
            for order_id in orders_proposal.cancel_order_ids:
                self.c_cancel_order(market_info, order_id)

        # Create orders.
        if actions & ORDER_PROPOSAL_ACTION_CREATE_ORDERS:
            if orders_proposal.buy_order_sizes[0] > 0:
                if orders_proposal.buy_order_type is OrderType.LIMIT and orders_proposal.buy_order_prices[0] > 0:
                    if self._logging_options & self.OPTION_LOG_CREATE_ORDER:
                        order_price_quote = zip(orders_proposal.buy_order_sizes, orders_proposal.buy_order_prices)
                        price_quote_str = [
                            f"{s.normalize()} {market_info.base_asset}, {p.normalize()} {market_info.quote_asset}"
                            for s, p in order_price_quote]
                        self.log_with_clock(
                            logging.INFO,
                            f"({market_info.trading_pair}) Creating limit bid orders at (Size, Price): {price_quote_str}"
                        )

                    for idx in range(len(orders_proposal.buy_order_sizes)):
                        bid_order_id = self.c_buy_with_specific_market(
                            market_info,
                            orders_proposal.buy_order_sizes[idx],
                            order_type=OrderType.LIMIT,
                            price=orders_proposal.buy_order_prices[idx],
                            expiration_seconds=expiration_seconds
                        )
                        self._time_to_cancel[bid_order_id] = self._current_timestamp + self._cancel_order_wait_time

                elif orders_proposal.buy_order_type is OrderType.MARKET:
                    raise RuntimeError("Market buy order in orders proposal is not supported yet.")

            if orders_proposal.sell_order_sizes[0] > 0:
                if orders_proposal.sell_order_type is OrderType.LIMIT and orders_proposal.sell_order_prices[0] > 0:
                    if self._logging_options & self.OPTION_LOG_CREATE_ORDER:
                        order_price_quote = zip(orders_proposal.sell_order_sizes, orders_proposal.sell_order_prices)
                        price_quote_str = [
                            f"{s.normalize()} {market_info.base_asset}, {p.normalize()} {market_info.quote_asset}"
                            for s, p in order_price_quote]
                        self.log_with_clock(
                            logging.INFO,
                            f"({market_info.trading_pair}) Creating limit ask orders at (Size, Price): {price_quote_str}"
                        )

                    for idx in range(len(orders_proposal.sell_order_sizes)):
                        ask_order_id = self.c_sell_with_specific_market(
                            market_info,
                            orders_proposal.sell_order_sizes[idx],
                            order_type=OrderType.LIMIT,
                            price=orders_proposal.sell_order_prices[idx],
                            expiration_seconds=expiration_seconds
                        )
                        self._time_to_cancel[ask_order_id] = self._current_timestamp + self._cancel_order_wait_time

                elif orders_proposal.sell_order_type is OrderType.MARKET:
                    raise RuntimeError("Market sell order in orders proposal is not supported yet.")
