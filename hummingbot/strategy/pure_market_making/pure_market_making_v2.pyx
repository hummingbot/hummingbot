from decimal import Decimal
import logging
from typing import (
    List,
    Tuple,
    Optional,
    Dict
)
from math import (
    floor,
    ceil
)

from hummingbot.core.clock cimport Clock
from hummingbot.core.event.events import TradeType
from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.market.market_base cimport MarketBase
from hummingbot.market.market_base import (
    MarketBase,
    OrderType,
    s_decimal_NaN
)
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_base import StrategyBase
from math import isnan

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
from .constant_size_sizing_delegate cimport ConstantSizeSizingDelegate
from .constant_size_sizing_delegate import ConstantSizeSizingDelegate
from .inventory_skew_single_size_sizing_delegate cimport InventorySkewSingleSizeSizingDelegate
from .inventory_skew_single_size_sizing_delegate import InventorySkewSingleSizeSizingDelegate
from .asset_price_delegate cimport AssetPriceDelegate
from .asset_price_delegate import AssetPriceDelegate


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

    # This is a temporary way to check if the mode of the strategy is of single order type,
    # for the replenish delay & enable_order_filled_stop_cancellation feature
    # Eventually this will be removed, as these will be rolled out across all modes
    SINGLE_ORDER_SIZING_DELEGATES = (ConstantSizeSizingDelegate, InventorySkewSingleSizeSizingDelegate)

    @classmethod
    def logger(cls):
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 market_infos: List[MarketTradingPairTuple],
                 filter_delegate: OrderFilterDelegate,
                 pricing_delegate: OrderPricingDelegate,
                 sizing_delegate: OrderSizingDelegate,
                 cancel_order_wait_time: float = 60,
                 filled_order_replenish_wait_time: float = 10,
                 enable_order_filled_stop_cancellation: bool = False,
                 add_transaction_costs_to_orders: bool = False,
                 best_bid_ask_jump_mode: bool = False,
                 best_bid_ask_jump_orders_depth: Decimal = s_decimal_zero,
                 logging_options: int = OPTION_LOG_ALL,
                 limit_order_min_expiration: float = 130.0,
                 status_report_interval: float = 900,
                 asset_price_delegate: AssetPriceDelegate = None,
                 expiration_seconds: float = NaN):

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
        self._expiration_seconds = expiration_seconds
        self._filled_order_replenish_wait_time = filled_order_replenish_wait_time
        self._add_transaction_costs_to_orders = add_transaction_costs_to_orders

        self._time_to_cancel = {}

        self._logging_options = logging_options
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval

        self._filter_delegate = filter_delegate
        self._pricing_delegate = pricing_delegate
        self._sizing_delegate = sizing_delegate
        self._enable_order_filled_stop_cancellation = enable_order_filled_stop_cancellation
        self._best_bid_ask_jump_mode = best_bid_ask_jump_mode
        self._best_bid_ask_jump_orders_depth = best_bid_ask_jump_orders_depth
        self._asset_price_delegate = asset_price_delegate

        self.limit_order_min_expiration = limit_order_min_expiration

        cdef:
            set all_markets = set([market_info.market for market_info in market_infos])

        self.c_add_markets(list(all_markets))

    @property
    def active_maker_orders(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return self._sb_order_tracker.active_maker_orders

    @property
    def market_info_to_active_orders(self) -> Dict[MarketTradingPairTuple, List[LimitOrder]]:
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
    def asset_price_delegate(self) -> AssetPriceDelegate:
        return self._asset_price_delegate

    @asset_price_delegate.setter
    def asset_price_delegate(self, value):
        self._asset_price_delegate = value

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
    def execute_orders_proposal(self, market_info: MarketTradingPairTuple, orders_proposal: OrdersProposal):
        return self.c_execute_orders_proposal(market_info, orders_proposal)

    def cancel_order(self, market_info: MarketTradingPairTuple, order_id: str):
        return self.c_cancel_order(market_info, order_id)

    def get_order_price_proposal(self, market_info: MarketTradingPairTuple) -> PricingProposal:
        asset_mid_price = Decimal("0")
        if self._asset_price_delegate is None:
            top_bid_price = market_info.get_price(False)
            top_ask_price = market_info.get_price(True)
            asset_mid_price = (top_bid_price + top_ask_price) * Decimal("0.5")
        else:
            asset_mid_price = self._asset_price_delegate.c_get_mid_price()
        active_orders = []
        for limit_order in self._sb_order_tracker.c_get_maker_orders().get(market_info, {}).values():
            if self._sb_order_tracker.c_has_in_flight_cancel(limit_order.client_order_id):
                continue
            active_orders.append(limit_order)

        return self._pricing_delegate.c_get_order_price_proposal(
            self, market_info, active_orders, asset_mid_price
        )

    def get_order_size_proposal(self, market_info: MarketTradingPairTuple, pricing_proposal: PricingProposal) -> SizingProposal:
        active_orders = []
        for limit_order in self._sb_order_tracker.c_get_maker_orders().get(market_info, {}).values():
            if self._sb_order_tracker.c_has_in_flight_cancel(limit_order.client_order_id):
                continue
            active_orders.append(limit_order)

        return self._sizing_delegate.c_get_order_size_proposal(
            self, market_info, active_orders, pricing_proposal
        )

    def get_orders_proposal_for_market_info(self,
                                            market_info: MarketTradingPairTuple,
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
                if self._asset_price_delegate is not None and self._all_markets_ready:
                    self._all_markets_ready = self._asset_price_delegate.ready
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
                                                                                   market_info_to_active_orders.get(market_info, []),
                                                                                   orders_proposal)
                filtered_proposal = self.c_filter_orders_proposal_for_takers(market_info, filtered_proposal)
                self.c_execute_orders_proposal(market_info, filtered_proposal)
        finally:
            self._last_timestamp = timestamp

    # To filter out any orders that are going to be taker orders, i.e. buy order price higher than first ask
    # and sell order price lower than first bid on the order book.
    cdef object c_filter_orders_proposal_for_takers(self, object market_info, object orders_proposal):
        cdef:
            list buy_prices = []
            list buy_sizes = []
            list sell_prices = []
            list sell_sizes = []
            MarketBase market = market_info.market
        if len(orders_proposal.buy_order_sizes) > 0 and orders_proposal.buy_order_sizes[0] > 0:
            first_ask = market.c_get_price(market_info.trading_pair, True)
            for buy_price, buy_size in zip(orders_proposal.buy_order_prices, orders_proposal.buy_order_sizes):
                if first_ask.is_nan() or (buy_price < first_ask):
                    buy_prices.append(buy_price)
                    buy_sizes.append(buy_size)
        if len(orders_proposal.sell_order_sizes) > 0 and orders_proposal.sell_order_sizes[0] > 0:
            first_bid = market.c_get_price(market_info.trading_pair, False)
            for sell_price, sell_size in zip(orders_proposal.sell_order_prices, orders_proposal.sell_order_sizes):
                if first_bid.is_nan() or (sell_price > first_bid):
                    sell_prices.append(sell_price)
                    sell_sizes.append(sell_size)
        return OrdersProposal(orders_proposal.actions,
                              orders_proposal.buy_order_type,
                              buy_prices,
                              buy_sizes,
                              orders_proposal.sell_order_type,
                              sell_prices,
                              sell_sizes,
                              orders_proposal.cancel_order_ids)

    # Compare the market price with the top bid and top ask price
    cdef object c_get_penny_jumped_pricing_proposal(self,
                                                    object market_info,
                                                    object pricing_proposal,
                                                    list active_orders):
        cdef:
            MarketBase maker_market = market_info.market
            OrderBook maker_orderbook = market_info.order_book
            object updated_buy_order_prices = pricing_proposal.buy_order_prices
            object updated_sell_order_prices = pricing_proposal.sell_order_prices
            object own_buy_order_depth = s_decimal_zero
            object own_sell_order_depth = s_decimal_zero

        active_orders = self.market_info_to_active_orders.get(market_info, [])

        # If there are multiple orders, do not jump prices
        if len(active_orders) > 2 or len(updated_buy_order_prices) > 1 or len(updated_sell_order_prices) > 1:
            return pricing_proposal

        for order in active_orders:
            if order.is_buy:
                own_buy_order_depth = order.quantity
            else:
                own_sell_order_depth = order.quantity

        # Get the top bid price in the market using best_bid_ask_jump_orders_depth and your buy order volume
        top_bid_price = market_info.get_price_for_volume(False,
                                                         self._best_bid_ask_jump_orders_depth + own_buy_order_depth).result_price
        price_quantum = maker_market.c_get_order_price_quantum(
            market_info.trading_pair,
            top_bid_price
        )
        # Get the price above the top bid
        price_above_bid = (ceil(top_bid_price / price_quantum) + 1) * price_quantum

        # If the price_above_bid is lower than the price suggested by the pricing proposal,
        # lower your price to this
        lower_buy_price = min(updated_buy_order_prices[0], price_above_bid)
        updated_buy_order_prices[0] = maker_market.c_quantize_order_price(market_info.trading_pair,
                                                                          lower_buy_price)

        # Get the top ask price in the market using best_bid_ask_jump_orders_depth and your sell order volume
        top_ask_price = market_info.get_price_for_volume(True,
                                                         self._best_bid_ask_jump_orders_depth + own_sell_order_depth).result_price
        price_quantum = maker_market.c_get_order_price_quantum(
            market_info.trading_pair,
            top_ask_price
        )
        # Get the price below the top ask
        price_below_ask = (floor(top_ask_price / price_quantum) - 1) * price_quantum

        # If the price_below_ask is higher than the price suggested by the pricing proposal,
        # increase your price to this
        higher_sell_price = max(updated_sell_order_prices[0], price_below_ask)
        updated_sell_order_prices[0] = maker_market.c_quantize_order_price(market_info.trading_pair,
                                                                           higher_sell_price)

        return PricingProposal(updated_buy_order_prices, updated_sell_order_prices)

    cdef tuple c_check_and_add_transaction_costs_to_pricing_proposal(self,
                                                                     object market_info,
                                                                     object pricing_proposal,
                                                                     object sizing_proposal):
        """
        1. Adds transaction costs to prices
        2. If the prices are negative, sets the do_not_place_order_flag to True, which stops order placement
        3. Returns the pricing proposal with transaction cost along with do_not_place_order
        :param market_info: Pure Market making Pair object
        :param pricing_proposal: Pricing Proposal
        :param sizing_proposal: Sizing Proposal
        :return: (do_not_place_order, Pricing_proposal_with_tx_costs)
        """
        cdef:
            MarketBase maker_market = market_info.market
            OrderBook maker_orderbook = market_info.order_book
            object buy_prices_with_tx_costs = pricing_proposal.buy_order_prices
            object sell_prices_with_tx_costs = pricing_proposal.sell_order_prices
            int64_t current_tick = <int64_t>(self._current_timestamp // self._status_report_interval)
            int64_t last_tick = <int64_t>(self._last_timestamp // self._status_report_interval)
            bint do_not_place_order = False
            bint should_report_warnings = ((current_tick > last_tick) and
                                           (self._logging_options & self.OPTION_LOG_STATUS_REPORT))
            # Current warning report threshold is 10%
            # If the adjusted price with transaction cost is 10% away from the suggested price,
            # warnings will be displayed
            object warning_report_threshold = Decimal("0.1")

        # If both buy order and sell order sizes are zero, no need to add transaction costs
        # as no new orders are created
        if sizing_proposal.buy_order_sizes[0] == s_decimal_zero and \
                sizing_proposal.sell_order_sizes[0] == s_decimal_zero:
            return do_not_place_order, pricing_proposal

        buy_index = 0
        for buy_price, buy_amount in zip(pricing_proposal.buy_order_prices,
                                         sizing_proposal.buy_order_sizes):
            if buy_amount > s_decimal_zero:
                fee_object = maker_market.c_get_fee(
                    market_info.base_asset,
                    market_info.quote_asset,
                    OrderType.LIMIT,
                    TradeType.BUY,
                    buy_amount,
                    buy_price
                )
                # Total flat fees charged by the exchange
                total_flat_fees = self.c_sum_flat_fees(market_info.quote_asset,
                                                       fee_object.flat_fees)
                # Find the fixed cost per unit size for the total amount
                # Fees is in Float
                fixed_cost_per_unit = total_flat_fees / buy_amount
                # New Price = Price * (1 - maker_fees) - Fixed_fees_per_unit
                buy_price_with_tx_cost = buy_price * (Decimal(1) - fee_object.percent) - fixed_cost_per_unit
            else:
                buy_price_with_tx_cost = buy_price

            buy_price_with_tx_cost = maker_market.c_quantize_order_price(market_info.trading_pair,
                                                                         buy_price_with_tx_cost)

            # If the buy price with transaction cost is less than or equal to zero
            # do not place orders
            if buy_price_with_tx_cost <= s_decimal_zero:
                if should_report_warnings:
                    self.logger().warning(f"Buy price with transaction cost is "
                                          f"less than or equal to zero. Stopping Order placements. ")
                do_not_place_order = True
                break

            # If the buy price with the transaction cost is 10% below the buy price due to price adjustment,
            # Display warning
            if (buy_price_with_tx_cost / buy_price) < (Decimal(1) - warning_report_threshold):
                if should_report_warnings:
                    self.logger().warning(f"Buy price with transaction cost is "
                                          f"{warning_report_threshold * 100} % below the buy price ")

            buy_prices_with_tx_costs[buy_index] = buy_price_with_tx_cost
            buy_index += 1

        if do_not_place_order:
            return do_not_place_order, pricing_proposal

        sell_index = 0
        for sell_price, sell_amount in zip(pricing_proposal.sell_order_prices,
                                           sizing_proposal.sell_order_sizes):
            if sell_amount > s_decimal_zero:
                fee_object = maker_market.c_get_fee(
                    market_info.base_asset,
                    market_info.quote_asset,
                    OrderType.LIMIT,
                    TradeType.SELL,
                    sell_amount,
                    sell_price
                )
                # Total flat fees charged by the exchange
                total_flat_fees = self.c_sum_flat_fees(market_info.quote_asset,
                                                       fee_object.flat_fees)
                # Find the fixed cost per unit size for the total amount
                # Fees is in Float
                fixed_cost_per_unit = total_flat_fees / sell_amount
                # New Price = Price * (1 + maker_fees) + Fixed_fees_per_unit
                sell_price_with_tx_cost = sell_price * (Decimal(1) + fee_object.percent) + fixed_cost_per_unit
            else:
                sell_price_with_tx_cost = sell_price

            sell_price_with_tx_cost = maker_market.c_quantize_order_price(market_info.trading_pair,
                                                                          Decimal(sell_price_with_tx_cost))

            if (sell_price_with_tx_cost / sell_price) > (Decimal(1) + warning_report_threshold):
                if should_report_warnings:
                    self.logger().warning(f"Sell price with transaction cost is "
                                          f"{warning_report_threshold * 100} % above the sell price")

            sell_prices_with_tx_costs[sell_index] = sell_price_with_tx_cost
            sell_index += 1

        return (do_not_place_order,
                PricingProposal(buy_prices_with_tx_costs, sell_prices_with_tx_costs))

    cdef object c_get_orders_proposal_for_market_info(self, object market_info, list active_orders):
        cdef:
            int actions = 0
            list cancel_order_ids = []
            bint no_order_placement = False

        # Before doing anything, ask the filter delegate whether to proceed or not.
        if not self._filter_delegate.c_should_proceed_with_processing(self, market_info, active_orders):
            return self.NO_OP_ORDERS_PROPOSAL

        # If there are no active orders, then do the following:
        #  1. Ask the pricing delegate on what are the order prices.
        #  2. Ask the sizing delegate on what are the order sizes.
        #  3. Set the actions to carry out in the orders proposal to include create orders.

        asset_mid_price = Decimal("0")
        if self._asset_price_delegate is None:
            asset_mid_price = market_info.get_mid_price()
        else:
            asset_mid_price = self._asset_price_delegate.c_get_mid_price()
        pricing_proposal = self._pricing_delegate.c_get_order_price_proposal(self,
                                                                             market_info,
                                                                             active_orders,
                                                                             asset_mid_price)
        # If jump orders is enabled, run the penny jumped pricing proposal
        if self._best_bid_ask_jump_mode:
            pricing_proposal = self.c_get_penny_jumped_pricing_proposal(market_info,
                                                                        pricing_proposal,
                                                                        active_orders)

        sizing_proposal = self._sizing_delegate.c_get_order_size_proposal(self,
                                                                          market_info,
                                                                          active_orders,
                                                                          pricing_proposal)
        if self._add_transaction_costs_to_orders:
            no_order_placement, pricing_proposal = self.c_check_and_add_transaction_costs_to_pricing_proposal(
                market_info,
                pricing_proposal,
                sizing_proposal)

        if sizing_proposal.buy_order_sizes[0] > 0 or sizing_proposal.sell_order_sizes[0] > 0:
            actions |= ORDER_PROPOSAL_ACTION_CREATE_ORDERS

        if no_order_placement:
            # Order creation bit is set to zero
            actions = actions & (1 << 1)

        if ((market_info.market.name not in self.RADAR_RELAY_TYPE_EXCHANGES) or
                (market_info.market.display_name == "bamboo_relay" and market_info.market.use_coordinator)):
            for active_order in active_orders:
                # If there are active orders, and active order cancellation is needed, then do the following:
                #  1. Check the time to cancel for each order, and see if cancellation should be proposed.
                #  2. Record each order id that needs to be cancelled.
                #  3. Set action to include cancel orders.

                # If Enable filled order stop cancellation is true and an order filled event happens when proposal is
                # generated, then check if the order is still in time_to_cancel

                if active_order.client_order_id in self._time_to_cancel and \
                        self._current_timestamp >= self._time_to_cancel[active_order.client_order_id]:
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
            MarketBase maker_market = market_info.market
            LimitOrder limit_order_record

        if isinstance(self.sizing_delegate, self.SINGLE_ORDER_SIZING_DELEGATES):
            # Set the replenish time as current_timestamp + order replenish time
            replenish_time_stamp = self._current_timestamp + self._filled_order_replenish_wait_time

            active_orders = self.market_info_to_active_orders.get(market_info, [])
            active_buy_orders = [x.client_order_id for x in active_orders if x.is_buy]
            active_sell_orders = [x.client_order_id for x in active_orders if not x.is_buy]

            if self._enable_order_filled_stop_cancellation:
                # If the filled order is a hanging order (not an active buy order)
                # do nothing
                if order_id not in active_buy_orders:
                    return

            # if filled order is buy, adjust the cancel time for sell order
            # For syncing buy and sell orders during order completed events
            for other_order_id in active_sell_orders:
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
                    maker_market.c_stop_tracking_order(other_order_id)

            if not isnan(replenish_time_stamp):
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
            MarketBase maker_market = market_info.market
            LimitOrder limit_order_record

        if isinstance(self.sizing_delegate, self.SINGLE_ORDER_SIZING_DELEGATES):
            # Set the replenish time as current_timestamp + order replenish time
            replenish_time_stamp = self._current_timestamp + self._filled_order_replenish_wait_time

            active_orders = self.market_info_to_active_orders.get(market_info, [])
            active_buy_orders = [x.client_order_id for x in active_orders if x.is_buy]
            active_sell_orders = [x.client_order_id for x in active_orders if not x.is_buy]

            if self._enable_order_filled_stop_cancellation:
                # If the filled order is a hanging order (not an active sell order)
                # do nothing
                if order_id not in active_sell_orders:
                    return

            # if filled order is sell, adjust the cancel time for buy order
            # For syncing buy and sell orders during order completed events
            for other_order_id in active_buy_orders:
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
                    maker_market.c_stop_tracking_order(other_order_id)

            if not isnan(replenish_time_stamp):
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
            if len(orders_proposal.buy_order_sizes) > 0 and orders_proposal.buy_order_sizes[0] > 0:
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

            if len(orders_proposal.sell_order_sizes) > 0 and orders_proposal.sell_order_sizes[0] > 0:
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
