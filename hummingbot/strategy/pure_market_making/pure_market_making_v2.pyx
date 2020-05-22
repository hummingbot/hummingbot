from decimal import Decimal
import logging
import pandas as pd
from typing import (
    List,
    Tuple,
    Dict,
    Optional
)
from math import (
    floor,
    ceil
)
import time
import numpy as np
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
from hummingbot.client.config.global_config_map import paper_trade_disabled
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
from .inventory_skew_calculator cimport c_calculate_bid_ask_ratios_from_base_asset_ratio


NaN = float("nan")
s_decimal_zero = Decimal(0)
s_decimal_neg_one = Decimal(-1)
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
    # for the replenish delay & hanging_orders_enabled feature
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
                 order_refresh_time: float = 30,
                 filled_order_delay: float = 60,
                 hanging_orders_enabled: bool = False,
                 add_transaction_costs_to_orders: bool = False,
                 order_optimization_enabled: bool = False,
                 order_optimization_depth: Decimal = s_decimal_zero,
                 logging_options: int = OPTION_LOG_ALL,
                 limit_order_min_expiration: float = 130.0,
                 status_report_interval: float = 900,
                 asset_price_delegate: AssetPriceDelegate = None,
                 expiration_seconds: float = NaN,
                 price_ceiling: Decimal = s_decimal_neg_one,
                 price_floor: Decimal = s_decimal_neg_one,
                 ping_pong_enabled: bool = False,
                 hanging_orders_cancel_pct: float = 0.1,
                 order_refresh_tolerance_pct: float = -1.0):

        if len(market_infos) < 1:
            raise ValueError(f"market_infos must not be empty.")
        if price_ceiling != s_decimal_neg_one and price_ceiling < price_floor:
            raise ValueError("Parameter price_ceiling cannot be lower than price_floor.")

        super().__init__()
        self._sb_order_tracker = PureMarketMakingOrderTracker()
        self._market_infos = {
            (market_info.market, market_info.trading_pair): market_info
            for market_info in market_infos
        }
        self._order_refresh_tolerance_pct = order_refresh_tolerance_pct
        self._cancel_timestamp = 0
        self._create_timestamp = 0
        self._limit_order_type = OrderType.LIMIT
        if any(m.market.name == "binance" for m in market_infos) and paper_trade_disabled():
            self._limit_order_type = OrderType.LIMIT_MAKER
        self._all_markets_ready = False
        self._order_refresh_time = order_refresh_time
        self._expiration_seconds = expiration_seconds
        self._price_ceiling = price_ceiling
        self._price_floor = price_floor
        self._ping_pong_enabled = ping_pong_enabled
        self._executed_bids_balance = 0
        self._executed_asks_balance = 0
        self._filled_order_delay = filled_order_delay
        self._add_transaction_costs_to_orders = add_transaction_costs_to_orders

        self._time_to_cancel = {}
        self._hanging_order_ids = []

        self._logging_options = logging_options
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval

        self._filter_delegate = filter_delegate
        self._pricing_delegate = pricing_delegate
        self._sizing_delegate = sizing_delegate
        self._hanging_orders_enabled = hanging_orders_enabled
        self._hanging_orders_cancel_pct = hanging_orders_cancel_pct
        self._order_optimization_enabled = order_optimization_enabled
        self._order_optimization_depth = order_optimization_depth
        self._asset_price_delegate = asset_price_delegate

        self.limit_order_min_expiration = limit_order_min_expiration

        cdef:
            set all_markets = set([market_info.market for market_info in market_infos])

        self.c_add_markets(list(all_markets))

    @property
    def hanging_order_ids(self) -> List[str]:
        return self._hanging_order_ids

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

    def inventory_skew_stats_data_frame(self, market_info: MarketTradingPairTuple) -> Optional[pd.DataFrame]:
        cdef:
            MarketBase market = market_info.market

        if (hasattr(self._sizing_delegate, "inventory_target_base_ratio") and
                hasattr(self._sizing_delegate, "inventory_range_multiplier") and
                hasattr(self._sizing_delegate, "total_order_size")):
            trading_pair = market_info.trading_pair
            mid_price = ((market.c_get_price(trading_pair, True) + market.c_get_price(trading_pair, False)) *
                         Decimal("0.5"))
            base_asset_amount = market.c_get_balance(market_info.base_asset)
            quote_asset_amount = market.c_get_balance(market_info.quote_asset)
            base_asset_value = base_asset_amount * mid_price
            quote_asset_value = quote_asset_amount / mid_price if mid_price > s_decimal_zero else s_decimal_zero
            total_value = base_asset_amount + quote_asset_value
            total_value_in_quote = (base_asset_amount * mid_price) + quote_asset_amount

            base_asset_ratio = (base_asset_amount / total_value
                                if total_value > s_decimal_zero
                                else s_decimal_zero)
            quote_asset_ratio = Decimal("1") - base_asset_ratio if total_value > 0 else 0
            target_base_ratio = self._sizing_delegate.inventory_target_base_ratio
            inventory_range_multiplier = self._sizing_delegate.inventory_range_multiplier
            target_base_amount = (total_value * target_base_ratio
                                  if mid_price > s_decimal_zero
                                  else s_decimal_zero)
            target_base_amount_in_quote = target_base_ratio * total_value_in_quote
            target_quote_amount = (1 - target_base_ratio) * total_value_in_quote
            base_asset_range = (self._sizing_delegate.total_order_size *
                                self._sizing_delegate.inventory_range_multiplier)
            high_water_mark = target_base_amount + base_asset_range
            low_water_mark = max(target_base_amount - base_asset_range, s_decimal_zero)
            low_water_mark_ratio = (low_water_mark / total_value
                                    if total_value > s_decimal_zero
                                    else s_decimal_zero)
            high_water_mark_ratio = (high_water_mark / total_value
                                     if total_value > s_decimal_zero
                                     else s_decimal_zero)
            high_water_mark_ratio = min(1.0, high_water_mark_ratio)
            total_order_size_ratio = (self._sizing_delegate.total_order_size / total_value
                                      if total_value > s_decimal_zero
                                      else s_decimal_zero)
            bid_ask_ratios = c_calculate_bid_ask_ratios_from_base_asset_ratio(
                float(base_asset_amount),
                float(quote_asset_amount),
                float(mid_price),
                float(target_base_ratio),
                float(base_asset_range)
            )
            inventory_skew_df = pd.DataFrame(data=[
                [f"Target Value ({market_info.quote_asset})", f"{target_base_amount_in_quote:.4f}",
                 f"{target_quote_amount:.4f}"],
                ["Current %", f"{base_asset_ratio:.1%}", f"{quote_asset_ratio:.1%}"],
                ["Target %", f"{target_base_ratio:.1%}", f"{1 - target_base_ratio:.1%}"],
                ["Inventory Range", f"{low_water_mark_ratio:.1%} - {high_water_mark_ratio:.1%}",
                 f"{1 - high_water_mark_ratio:.1%} - {1 - low_water_mark_ratio:.1%}"],
                ["Order Adjust %", f"{bid_ask_ratios.bid_ratio:.1%}", f"{bid_ask_ratios.ask_ratio:.1%}"]
            ])
            return inventory_skew_df
        else:
            return None

    def pure_mm_assets_df(self, market_info: MarketTradingPairTuple, to_show_current_pct: bool) -> pd.DataFrame:
        market, trading_pair, base_asset, quote_asset = market_info
        active_orders = self.market_info_to_active_orders.get(market_info, [])
        mid_price = market_info.get_mid_price()
        base_balance = float(market.get_balance(base_asset))
        quote_balance = float(market.get_balance(quote_asset))
        available_base_balance = float(market.get_available_balance(base_asset))
        available_quote_balance = float(market.get_available_balance(quote_asset))
        base_value = base_balance * float(mid_price)
        total_in_quote = base_value + quote_balance
        base_ratio = base_value / total_in_quote if total_in_quote > 0 else 0
        quote_ratio = quote_balance / total_in_quote if total_in_quote > 0 else 0
        data=[
            ["", base_asset, quote_asset],
            ["Total Balance", round(base_balance, 4), round(quote_balance, 4)],
            ["Available Balance", round(available_base_balance, 4), round(available_quote_balance, 4)],
            [f"Current Value ({quote_asset})", round(base_value, 4), round(quote_balance, 4)]
        ]
        if to_show_current_pct:
            data.append(["Current %", f"{base_ratio:.1%}", f"{quote_ratio:.1%}"])
        df = pd.DataFrame(data=data)
        return df

    def active_orders_df(self, market_info) -> pd.DataFrame:
        mid_price = market_info.get_mid_price()
        active_orders = self.market_info_to_active_orders.get(market_info, [])
        no_sells = len([o for o in active_orders if not o.is_buy and o.client_order_id not in self._hanging_order_ids])
        active_orders.sort(key=lambda x: x.price, reverse=True)
        columns = ["Level", "Type", "Price", "Spread", "Amount (Orig)", "Amount (Adj)", "Age", "Hang"]
        data = []
        order_start_size = 0
        if hasattr(self._sizing_delegate, "order_start_size"):
            order_start_size = self._sizing_delegate.order_start_size
        elif hasattr(self._sizing_delegate, "order_size"):
            order_start_size = self._sizing_delegate.order_size
        order_step_size = 0
        if hasattr(self._sizing_delegate, "order_step_size"):
            order_step_size = self._sizing_delegate.order_step_size
        lvl_buy, lvl_sell = 0, 0
        for idx in range(0, len(active_orders)):
            order = active_orders[idx]
            level = None
            if order.client_order_id not in self._hanging_order_ids:
                if order.is_buy:
                    level = lvl_buy + 1
                    lvl_buy += 1
                else:
                    level = no_sells - lvl_sell
                    lvl_sell += 1
            spread = 0 if mid_price == 0 else abs(order.price - mid_price)/mid_price
            age = "n/a"
            # // indicates order is a paper order so 'n/a'. For real orders, calculate age.
            if "//" not in order.client_order_id:
                age = pd.Timestamp(int(time.time()) - int(order.client_order_id[-16:])/1e6,
                                   unit='s').strftime('%H:%M:%S')
            amount_orig = "" if level is None else order_start_size + ((level - 1) * order_step_size)
            data.append([
                "" if level is None else level,
                "buy" if order.is_buy else "sell",
                float(order.price),
                f"{spread:.2%}",
                amount_orig,
                float(order.quantity),
                age,
                "yes" if order.client_order_id in self._hanging_order_ids else "no"
            ])

        return pd.DataFrame(data=data, columns=columns)

    def format_status(self) -> str:
        cdef:
            list lines = []
            list warning_lines = []
            list active_orders = []

        for market_info in self._market_infos.values():
            active_orders = self.market_info_to_active_orders.get(market_info, [])

            warning_lines.extend(self.network_warning([market_info]))

            markets_df = self.market_status_data_frame([market_info])
            lines.extend(["", "  Markets:"] + ["    " + line for line in markets_df.to_string(index=False).split("\n")])

            inventory_skew_df = self.inventory_skew_stats_data_frame(market_info)
            assets_df = self.pure_mm_assets_df(market_info, inventory_skew_df is None)

            # append inventory skew stats.
            if inventory_skew_df is not None:
                assets_df = assets_df.append(inventory_skew_df)

            first_col_length = max(*assets_df[0].apply(len))
            df_lines = assets_df.to_string(index=False, header=False,
                                           formatters={0: ("{:<" + str(first_col_length) + "}").format}).split("\n")
            lines.extend(["", "  Assets:"] + ["    " + line for line in df_lines])

            # See if there're any open orders.
            if len(active_orders) > 0:
                df = self.active_orders_df(market_info)
                lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
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
                active_orders = market_info_to_active_orders.get(market_info, [])
                active_non_hangings = [o for o in active_orders if o.client_order_id not in self._hanging_order_ids]

                print(f"\n<c_tick> active_non_hangings -> {active_non_hangings}\n")

                try:
                    if self._create_timestamp <= self._current_timestamp:
                        orders_proposal = self.c_create_orders_proposals(
                            market_info,
                            active_orders
                        )
                except Exception:
                    self.logger().error("Unknown error while generating order proposals.", exc_info=True)
                finally:
                    self._sb_delegate_lock = False
                self.c_cancel_active_orders(market_info, orders_proposal)
                self.c_cancel_hanging_orders(market_info)
                self.c_execute_orders_proposal(market_info, orders_proposal)
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

        # Get the top bid price in the market using order_optimization_depth and your buy order volume
        top_bid_price = market_info.get_price_for_volume(False,
                                                         self._order_optimization_depth + own_buy_order_depth).result_price
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

        # Get the top ask price in the market using order_optimization_depth and your sell order volume
        top_ask_price = market_info.get_price_for_volume(True,
                                                         self._order_optimization_depth + own_sell_order_depth).result_price
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

    cdef tuple c_check_and_apply_ping_pong_strategy(self, object sizing_proposal, object pricing_proposal):
        """
        Removes bid/ask orders in accordance with the ping-pong strategy.

        :param sizing_proposal: The current sizing proposal.
        :param pricing_proposal: The current pricing proposal.
        :return: Revised sizing and pricing proposals.
        """
        cdef:
            list buy_order_sizes = [order_size for order_size in sizing_proposal.buy_order_sizes]
            list buy_order_prices = [order_price for order_price in pricing_proposal.buy_order_prices]
            list sell_order_sizes = [order_size for order_size in sizing_proposal.sell_order_sizes]
            list sell_order_prices = [order_price for order_price in pricing_proposal.sell_order_prices]

        print(f"ask_balance {self._executed_asks_balance} - bid_balance {self._executed_bids_balance}")

        if self._executed_asks_balance == self._executed_bids_balance:
            self._executed_asks_balance = self._executed_bids_balance = 0
        if self._ping_pong_enabled:
            if self._executed_bids_balance != 0:
                buy_order_sizes = buy_order_sizes[self._executed_bids_balance:]
                buy_order_prices = buy_order_prices[self._executed_bids_balance:]
            elif self._executed_asks_balance != 0:
                sell_order_sizes = sell_order_sizes[self._executed_asks_balance:]
                sell_order_prices = sell_order_prices[self._executed_asks_balance:]

        return (SizingProposal(buy_order_sizes, sell_order_sizes),
                PricingProposal(buy_order_prices, sell_order_prices))

    cdef object c_check_and_apply_price_bands_to_sizing_proposal(self,
                                                                 object market_info,
                                                                 object sizing_proposal):
        """
        Sets bid/ask order size to zero if current price is above/below price band limits.

        :param market_info: Pure Market making Pair object.
        :param sizing_proposal: The current sizing proposal.
        :return: revised_sizing_proposal
        """
        cdef:
            list buy_order_sizes = [order_size for order_size in sizing_proposal.buy_order_sizes]
            list sell_order_sizes = [order_size for order_size in sizing_proposal.sell_order_sizes]

        if self._asset_price_delegate is None:
            asset_mid_price = market_info.get_mid_price()
        else:
            asset_mid_price = self._asset_price_delegate.c_get_mid_price()

        if self._price_ceiling != s_decimal_neg_one and asset_mid_price > self._price_ceiling:
            buy_order_sizes = [s_decimal_zero for order_size in sizing_proposal.buy_order_sizes]
        if self._price_floor != s_decimal_neg_one and asset_mid_price < self._price_floor:
            sell_order_sizes = [s_decimal_zero for order_size in sizing_proposal.sell_order_sizes]

        return SizingProposal(buy_order_sizes, sell_order_sizes)

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

    cdef object c_create_orders_proposals(self, object market_info, list active_orders):
        active_non_hanging_orders = [o for o in active_orders if o.client_order_id not in self._hanging_order_ids]
        asset_mid_price = Decimal("0")
        if self._asset_price_delegate is None:
            asset_mid_price = market_info.get_mid_price()
        else:
            asset_mid_price = self._asset_price_delegate.c_get_mid_price()
        pricing_proposal = self._pricing_delegate.c_get_order_price_proposal(self,
                                                                             market_info,
                                                                             active_non_hanging_orders,
                                                                             asset_mid_price)
        # If jump orders is enabled, run the penny jumped pricing proposal
        if self._order_optimization_enabled:
            pricing_proposal = self.c_get_penny_jumped_pricing_proposal(market_info,
                                                                        pricing_proposal,
                                                                        active_non_hanging_orders)

        sizing_proposal = self._sizing_delegate.c_get_order_size_proposal(self,
                                                                          market_info,
                                                                          active_non_hanging_orders,
                                                                          pricing_proposal)
        sizing_proposal, pricing_proposal = self.c_check_and_apply_ping_pong_strategy(sizing_proposal,
                                                                                      pricing_proposal)
        sizing_proposal = self.c_check_and_apply_price_bands_to_sizing_proposal(market_info,
                                                                                sizing_proposal)

        if self._add_transaction_costs_to_orders:
            no_order_placement, pricing_proposal = self.c_check_and_add_transaction_costs_to_pricing_proposal(
                market_info,
                pricing_proposal,
                sizing_proposal)

        return OrdersProposal(0,
                              self._limit_order_type,
                              pricing_proposal.buy_order_prices,
                              sizing_proposal.buy_order_sizes,
                              self._limit_order_type,
                              pricing_proposal.sell_order_prices,
                              sizing_proposal.sell_order_sizes,
                              [])

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

        active_orders = self.market_info_to_active_orders.get(market_info, [])
        active_buy_orders = [x.client_order_id for x in active_orders if x.is_buy]
        active_sell_orders = [x.client_order_id for x in active_orders if not x.is_buy]

        if self._hanging_orders_enabled:
            # If the filled order is a hanging order, do nothing
            if order_id in self._hanging_order_ids:
                return

        # delay order creation by filled_order_dalay (in seconds)
        self._create_timestamp = self._current_timestamp + self._filled_order_delay
        self._cancel_timestamp = min(self._cancel_timestamp, self._create_timestamp)

        if self._hanging_orders_enabled:
            for other_order_id in active_sell_orders:
                self._hanging_order_ids.append(other_order_id)

        if market_info is not None:
            self._executed_bids_balance += 1
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

        active_orders = self.market_info_to_active_orders.get(market_info, [])
        active_buy_orders = [x.client_order_id for x in active_orders if x.is_buy]
        active_sell_orders = [x.client_order_id for x in active_orders if not x.is_buy]

        if self._hanging_orders_enabled:
            # If the filled order is a hanging order, do nothing
            if order_id in self._hanging_order_ids:
                return

        # delay order creation by filled_order_dalay (in seconds)
        self._create_timestamp = self._current_timestamp + self._filled_order_delay
        self._cancel_timestamp = min(self._cancel_timestamp, self._create_timestamp)

        if self._hanging_orders_enabled:
            for other_order_id in active_buy_orders:
                self._hanging_order_ids.append(other_order_id)

        if market_info is not None:
            self._executed_asks_balance += 1
            limit_order_record = self._sb_order_tracker.c_get_limit_order(market_info, order_id)
            self.log_with_clock(
                logging.INFO,
                f"({market_info.trading_pair}) Maker sell order {order_id} "
                f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
            )

    cdef bint c_is_within_tolerance(self, list current_orders, list proposals):
        if len(current_orders) != len(proposals):
            return False
        current_orders = sorted(current_orders, key=lambda x: x[1])
        proposals = sorted(proposals, key=lambda x: x[0])
        cdef object tolerance = Decimal(str(self._order_refresh_tolerance_pct))
        for current, proposal in zip(current_orders, proposals):
            # if spread diff is more than the tolerance or order quantities are different, return false.
            if abs(proposal[0] - current[1])/current[1] > tolerance:
                return False
        return True

    cdef c_join_price_size_proposals(self, list prices, list sizes):
        cdef list result = list(zip(prices, sizes))
        result = [x for x in result if x[0] > 0 and x[1] > 0]
        return result

    # Cancel active non hanging orders
    # Return value: whether order cancellation is deferred.
    cdef c_cancel_active_orders(self, object market_info, object orders_proposal):
        if self._cancel_timestamp > self._current_timestamp:
            return
        cdef:
            list active_orders = self.market_info_to_active_orders.get(market_info, [])
            list buy_proposals = []
            list sell_proposals = []
            list active_buys = []
            list active_sells = []
            bint to_defer_canceling = False
        active_orders = [o for o in active_orders if o.client_order_id not in self._hanging_order_ids]

        print(f"active_orders {active_orders}")

        if len(active_orders) == 0:
            return
        if orders_proposal is not None and self._order_refresh_tolerance_pct >= 0:
            buy_proposals = self.c_join_price_size_proposals(orders_proposal.buy_order_prices,
                                                             orders_proposal.buy_order_sizes)
            sell_proposals = self.c_join_price_size_proposals(orders_proposal.sell_order_prices,
                                                              orders_proposal.sell_order_sizes)
            active_buys = [[o.client_order_id, Decimal(str(o.price)), Decimal(str(o.quantity))]
                           for o in active_orders if o.is_buy]
            active_sells = [[o.client_order_id, Decimal(str(o.price)), Decimal(str(o.quantity))]
                            for o in active_orders if not o.is_buy]
            if self.c_is_within_tolerance(active_buys, buy_proposals) and \
                    self.c_is_within_tolerance(active_sells, sell_proposals):
                to_defer_canceling = True

        print(f"to_defer_canceling {to_defer_canceling}")

        if not to_defer_canceling:
            for order in active_orders:
                self.c_cancel_order(market_info, order.client_order_id)
            # This is only for unit testing purpose as some test cases expect order creation to happen in the next tick.
            # In production, order creation always happens in another cycle as it first checks for no active orders.
            if self._create_timestamp <= self._current_timestamp:
                self._create_timestamp = self._current_timestamp + 0.1
        else:
            self.logger().info(f"Not cancelling active orders since difference between new order prices "
                               f"and current order prices is within "
                               f"{self._order_refresh_tolerance_pct:.2%} order_refresh_tolerance_pct")
            self.set_timers()

    cdef c_cancel_hanging_orders(self, object market_info):
        if not self._hanging_orders_enabled:
            return
        cdef:
            object mid_price = market_info.get_mid_price()
            list active_orders = self.market_info_to_active_orders.get(market_info, [])
            list orders
            LimitOrder order
        for h_order_id in self._hanging_order_ids:
            orders = [o for o in active_orders if o.client_order_id == h_order_id]
            if orders and mid_price > 0:
                order = orders[0]
                if abs(order.price - mid_price)/mid_price >= self._hanging_orders_cancel_pct:
                    self.c_cancel_order(market_info, order.client_order_id)

    cdef bint c_to_create_orders(self, object market_info, object orders_proposal):
        if self._create_timestamp > self._current_timestamp or orders_proposal is None:

            print(f"c_to_create_orders returning False, {self._create_timestamp} > {self._current_timestamp}")

            return False
        cdef:
            list active_orders = self.market_info_to_active_orders.get(market_info, [])
        active_orders = [o for o in active_orders if o.client_order_id not in self._hanging_order_ids]

        print(f"c_to_create_orders returning {len(active_orders) == 0} (check)")

        return len(active_orders) == 0

    cdef c_execute_orders_proposal(self, object market_info, object orders_proposal):
        if not self.c_to_create_orders(market_info, orders_proposal):
            return
        cdef:
            double expiration_seconds = (self._order_refresh_time
                                         if ((market_info.market.name in self.RADAR_RELAY_TYPE_EXCHANGES) or
                                             (market_info.market.name == "bamboo_relay" and not market_info.market.use_coordinator))
                                         else NaN)
            str bid_order_id, ask_order_id
            bint orders_created = False
        orders_proposal = self.c_filter_orders_proposal_for_takers(market_info, orders_proposal)
        if len(orders_proposal.buy_order_sizes) > 0 and orders_proposal.buy_order_sizes[0] > 0:
            if orders_proposal.buy_order_type is self._limit_order_type and orders_proposal.buy_order_prices[0] > 0:
                if self._logging_options & self.OPTION_LOG_CREATE_ORDER:
                    order_price_quote = zip(orders_proposal.buy_order_sizes, orders_proposal.buy_order_prices)
                    price_quote_str = [
                        f"{s.normalize()} {market_info.base_asset}, {p.normalize()} {market_info.quote_asset}"
                        for s, p in order_price_quote]
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_info.trading_pair}) Creating {len(orders_proposal.buy_order_sizes)} bid orders "
                        f"at (Size, Price): {price_quote_str}"
                    )

                for idx in range(len(orders_proposal.buy_order_sizes)):
                    bid_order_id = self.c_buy_with_specific_market(
                        market_info,
                        orders_proposal.buy_order_sizes[idx],
                        order_type=self._limit_order_type,
                        price=orders_proposal.buy_order_prices[idx],
                        expiration_seconds=expiration_seconds
                    )
                    orders_created = True

            elif orders_proposal.buy_order_type is OrderType.MARKET:
                raise RuntimeError("Market buy order in orders proposal is not supported yet.")

        if len(orders_proposal.sell_order_sizes) > 0 and orders_proposal.sell_order_sizes[0] > 0:
            if orders_proposal.sell_order_type is self._limit_order_type and orders_proposal.sell_order_prices[0] > 0:
                if self._logging_options & self.OPTION_LOG_CREATE_ORDER:
                    order_price_quote = zip(orders_proposal.sell_order_sizes, orders_proposal.sell_order_prices)
                    price_quote_str = [
                        f"{s.normalize()} {market_info.base_asset}, {p.normalize()} {market_info.quote_asset}"
                        for s, p in order_price_quote]
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_info.trading_pair}) Creating {len(orders_proposal.sell_order_sizes)} ask "
                        f"orders at (Size, Price): {price_quote_str}"
                    )

                for idx in range(len(orders_proposal.sell_order_sizes)):
                    ask_order_id = self.c_sell_with_specific_market(
                        market_info,
                        orders_proposal.sell_order_sizes[idx],
                        order_type=self._limit_order_type,
                        price=orders_proposal.sell_order_prices[idx],
                        expiration_seconds=expiration_seconds
                    )
                    orders_created = True
            elif orders_proposal.sell_order_type is OrderType.MARKET:
                raise RuntimeError("Market sell order in orders proposal is not supported yet.")
        if orders_created:
            self.set_timers()

    cdef set_timers(self):
        cdef double next_cycle = self._current_timestamp + self._order_refresh_time
        if self._create_timestamp <= self._current_timestamp:
            self._create_timestamp = next_cycle
        if self._cancel_timestamp <= self._current_timestamp:
            self._cancel_timestamp = min(self._create_timestamp, next_cycle)
