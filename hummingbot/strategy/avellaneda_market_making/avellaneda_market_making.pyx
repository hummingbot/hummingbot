import datetime
from decimal import Decimal
import logging
from math import (
    floor,
    ceil,
    isnan
)
import numpy as np
import os
import pandas as pd
import time
from typing import (
    List,
    Dict,
    Tuple,
)

from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.clock cimport Clock
from hummingbot.core.event.events import TradeType
from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.event.events import OrderType

from hummingbot.strategy.__utils__.trailing_indicators.instant_volatility import InstantVolatilityIndicator
from hummingbot.strategy.__utils__.trailing_indicators.trading_intensity import TradingIntensityIndicator
from hummingbot.strategy.conditional_execution_state import (
    RunAlwaysExecutionState,
    RunInTimeConditionalExecutionState
)
from hummingbot.strategy.data_types import (
    Proposal,
    PriceSize)
from hummingbot.strategy.hanging_orders_tracker import (
    CreatedPairOfOrders,
    HangingOrdersTracker)
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.order_tracker cimport OrderTracker
from hummingbot.strategy.strategy_base import StrategyBase
from hummingbot.strategy.utils import order_age
from hummingbot.core.utils import map_df_to_str


NaN = float("nan")
s_decimal_zero = Decimal(0)
s_decimal_neg_one = Decimal(-1)
s_decimal_one = Decimal(1)
pmm_logger = None


cdef class AvellanedaMarketMakingStrategy(StrategyBase):
    OPTION_LOG_CREATE_ORDER = 1 << 3
    OPTION_LOG_MAKER_ORDER_FILLED = 1 << 4
    OPTION_LOG_STATUS_REPORT = 1 << 5
    OPTION_LOG_ALL = 0x7fffffffffffffff

    @classmethod
    def logger(cls):
        global pmm_logger
        if pmm_logger is None:
            pmm_logger = logging.getLogger(__name__)
        return pmm_logger

    def init_params(self,
                    market_info: MarketTradingPairTuple,
                    order_amount: Decimal,
                    order_refresh_time: float = 30.0,
                    max_order_age: float = 1800,
                    order_refresh_tolerance_pct: Decimal = s_decimal_neg_one,
                    order_optimization_enabled = True,
                    filled_order_delay: float = 60.0,
                    order_levels: int = 0,
                    level_distances: Decimal = Decimal("0.0"),
                    order_override: Dict[str, List[str]] = {},
                    hanging_orders_enabled: bool = False,
                    hanging_orders_cancel_pct: Decimal = Decimal("0.1"),
                    inventory_target_base_pct: Decimal = s_decimal_zero,
                    add_transaction_costs_to_orders: bool = True,
                    logging_options: int = OPTION_LOG_ALL,
                    status_report_interval: float = 900,
                    hb_app_notification: bool = False,
                    risk_factor: Decimal = Decimal("0.5"),
                    order_amount_shape_factor: Decimal = Decimal("0.0"),
                    execution_timeframe: str = "infinite",
                    execution_state: ConditionalExecutionState = RunAlwaysExecutionState(),
                    start_time: datetime.datetime = None,
                    end_time: datetime.datetime = None,
                    min_spread: Decimal = Decimal("0"),
                    debug_csv_path: str = '',
                    volatility_buffer_size: int = 200,
                    trading_intensity_buffer_size: int = 200,
                    trading_intensity_price_levels: Tuple[float] = tuple(np.geomspace(1, 2, 10) - 1),
                    should_wait_order_cancel_confirmation = True,
                    is_debug: bool = False,
                    ):
        self._sb_order_tracker = OrderTracker()
        self._market_info = market_info
        self._order_amount = order_amount
        self._order_optimization_enabled = order_optimization_enabled
        self._order_refresh_time = order_refresh_time
        self._max_order_age = max_order_age
        self._order_refresh_tolerance_pct = order_refresh_tolerance_pct
        self._filled_order_delay = filled_order_delay
        self._order_levels = order_levels
        self._level_distances = level_distances
        self._order_override = order_override
        self._inventory_target_base_pct = inventory_target_base_pct
        self._add_transaction_costs_to_orders = add_transaction_costs_to_orders
        self._hb_app_notification = hb_app_notification
        self._hanging_orders_enabled = hanging_orders_enabled
        self._hanging_orders_tracker = HangingOrdersTracker(self,
                                                            hanging_orders_cancel_pct)

        self._cancel_timestamp = 0
        self._create_timestamp = 0
        self._limit_order_type = self._market_info.market.get_maker_order_type()
        self._all_markets_ready = False
        self._filled_buys_balance = 0
        self._filled_sells_balance = 0
        self._logging_options = logging_options
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self._last_own_trade_price = Decimal('nan')

        self.c_add_markets([market_info.market])
        self._ticks_to_be_ready = max(volatility_buffer_size, trading_intensity_buffer_size)
        self._avg_vol = InstantVolatilityIndicator(sampling_length=volatility_buffer_size)
        self._trading_intensity = TradingIntensityIndicator(trading_intensity_buffer_size)
        self._last_sampling_timestamp = 0
        self._alpha = None
        self._kappa = None
        self._gamma = risk_factor
        self._eta = order_amount_shape_factor
        self._execution_timeframe = execution_timeframe
        self._execution_state = execution_state
        self._start_time = start_time
        self._end_time = end_time
        self._min_spread = min_spread
        self._latest_parameter_calculation_vol = s_decimal_zero
        self._reserved_price = s_decimal_zero
        self._optimal_spread = s_decimal_zero
        self._optimal_ask = s_decimal_zero
        self._optimal_bid = s_decimal_zero
        self._should_wait_order_cancel_confirmation = should_wait_order_cancel_confirmation
        self._debug_csv_path = debug_csv_path
        self._is_debug = is_debug
        try:
            if self._is_debug:
                os.unlink(self._debug_csv_path)
        except FileNotFoundError:
            pass

    def all_markets_ready(self):
        return all([market.ready for market in self._sb_markets])

    @property
    def latest_parameter_calculation_vol(self):
        return self._latest_parameter_calculation_vol

    @latest_parameter_calculation_vol.setter
    def latest_parameter_calculation_vol(self, value):
        self._latest_parameter_calculation_vol = value

    @property
    def min_spread(self):
        return self._min_spread

    @min_spread.setter
    def min_spread(self, value):
        self._min_spread = value

    @property
    def avg_vol(self):
        return self._avg_vol

    @avg_vol.setter
    def avg_vol(self, indicator: InstantVolatilityIndicator):
        self._avg_vol = indicator

    @property
    def trading_intensity(self):
        return self._trading_intensity

    @trading_intensity.setter
    def trading_intensity(self, indicator: TradingIntensityIndicator):
        self._trading_intensity = indicator

    @property
    def market_info(self) -> MarketTradingPairTuple:
        return self._market_info

    @property
    def order_refresh_tolerance_pct(self) -> Decimal:
        return self._order_refresh_tolerance_pct

    @order_refresh_tolerance_pct.setter
    def order_refresh_tolerance_pct(self, value: Decimal):
        self._order_refresh_tolerance_pct = value

    @property
    def order_amount(self) -> Decimal:
        return self._order_amount

    @order_amount.setter
    def order_amount(self, value: Decimal):
        self._order_amount = value

    @property
    def inventory_target_base_pct(self) -> Decimal:
        return self._inventory_target_base_pct

    @inventory_target_base_pct.setter
    def inventory_target_base_pct(self, value: Decimal):
        self._inventory_target_base_pct = value

    @property
    def order_optimization_enabled(self) -> bool:
        return self._order_optimization_enabled

    @order_optimization_enabled.setter
    def order_optimization_enabled(self, value: bool):
        self._order_optimization_enabled = value

    @property
    def order_refresh_time(self) -> float:
        return self._order_refresh_time

    @order_refresh_time.setter
    def order_refresh_time(self, value: float):
        self._order_refresh_time = value

    @property
    def filled_order_delay(self) -> float:
        return self._filled_order_delay

    @filled_order_delay.setter
    def filled_order_delay(self, value: float):
        self._filled_order_delay = value

    @property
    def order_override(self) -> Dict[str, any]:
        return self._order_override

    @order_override.setter
    def order_override(self, value):
        self._order_override = value

    @property
    def order_levels(self) -> int:
        return self._order_levels

    @order_levels.setter
    def order_levels(self, value):
        self._order_levels = value

    @property
    def level_distances(self) -> int:
        return self._level_distances

    @level_distances.setter
    def level_distances(self, value):
        self._level_distances = value

    @property
    def max_order_age(self):
        return self._max_order_age

    @max_order_age.setter
    def max_order_age(self, value):
        self._max_order_age = value

    @property
    def add_transaction_costs_to_orders(self) -> bool:
        return self._add_transaction_costs_to_orders

    @add_transaction_costs_to_orders.setter
    def add_transaction_costs_to_orders(self, value: bool):
        self._add_transaction_costs_to_orders = value

    @property
    def base_asset(self):
        return self._market_info.base_asset

    @property
    def quote_asset(self):
        return self._market_info.quote_asset

    @property
    def trading_pair(self):
        return self._market_info.trading_pair

    @property
    def gamma(self):
        return self._gamma

    @gamma.setter
    def gamma(self, value):
        self._gamma = value

    @property
    def alpha(self):
        return self._alpha

    @alpha.setter
    def alpha(self, value):
        self._alpha = value

    @property
    def kappa(self):
        return self._kappa

    @kappa.setter
    def kappa(self, value):
        self._kappa = value

    @property
    def eta(self):
        return self._eta

    @eta.setter
    def eta(self, value):
        self._eta = value

    @property
    def reserved_price(self):
        return self._reserved_price

    @reserved_price.setter
    def reserved_price(self, value):
        self._reserved_price = value

    @property
    def optimal_spread(self):
        return self._optimal_spread

    @property
    def optimal_ask(self):
        return self._optimal_ask

    @optimal_ask.setter
    def optimal_ask(self, value):
        self._optimal_ask = value

    @property
    def optimal_bid(self):
        return self._optimal_bid

    @optimal_bid.setter
    def optimal_bid(self, value):
        self._optimal_bid = value

    @property
    def execution_timeframe(self):
        return self._execution_timeframe

    @execution_timeframe.setter
    def execution_timeframe(self, value):
        self._execution_timeframe = value

    @property
    def start_time(self) -> time:
        return self._start_time

    @start_time.setter
    def start_time(self, value):
        self._start_time = value

    @property
    def end_time(self) -> time:
        return self._end_time

    @end_time.setter
    def end_time(self, value):
        self._end_time = value

    def get_price(self) -> float:
        return self.get_mid_price()

    def get_last_price(self) -> float:
        return self._market_info.get_last_price()

    def get_mid_price(self) -> float:
        return self.c_get_mid_price()

    cdef object c_get_mid_price(self):
        return self._market_info.get_mid_price()

    def get_order_book_snapshot(self) -> float:
        return self.c_get_order_book_snapshot()

    cdef object c_get_order_book_snapshot(self):
        return self._market_info.order_book.snapshot

    @property
    def market_info_to_active_orders(self) -> Dict[MarketTradingPairTuple, List[LimitOrder]]:
        return self._sb_order_tracker.market_pair_to_active_orders

    @property
    def active_orders(self) -> List[LimitOrder]:
        if self._market_info not in self.market_info_to_active_orders:
            return []
        return self.market_info_to_active_orders[self._market_info]

    @property
    def active_non_hanging_orders(self) -> List[LimitOrder]:
        orders = [o for o in self.active_orders if not self._hanging_orders_tracker.is_order_id_in_hanging_orders(o.client_order_id)]
        return orders

    @property
    def active_buys(self) -> List[LimitOrder]:
        return [o for o in self.active_orders if o.is_buy]

    @property
    def active_sells(self) -> List[LimitOrder]:
        return [o for o in self.active_orders if not o.is_buy]

    @property
    def logging_options(self) -> int:
        return self._logging_options

    @logging_options.setter
    def logging_options(self, int64_t logging_options):
        self._logging_options = logging_options

    @property
    def hanging_orders_tracker(self):
        return self._hanging_orders_tracker

    def pure_mm_assets_df(self, to_show_current_pct: bool) -> pd.DataFrame:
        market, trading_pair, base_asset, quote_asset = self._market_info
        price = self._market_info.get_mid_price()
        base_balance = float(market.get_balance(base_asset))
        quote_balance = float(market.get_balance(quote_asset))
        available_base_balance = float(market.get_available_balance(base_asset))
        available_quote_balance = float(market.get_available_balance(quote_asset))
        base_value = base_balance * float(price)
        total_in_quote = base_value + quote_balance
        base_ratio = base_value / total_in_quote if total_in_quote > 0 else 0
        quote_ratio = quote_balance / total_in_quote if total_in_quote > 0 else 0
        data = [
            ["", base_asset, quote_asset],
            ["Total Balance", round(base_balance, 4), round(quote_balance, 4)],
            ["Available Balance", round(available_base_balance, 4), round(available_quote_balance, 4)],
            [f"Current Value ({quote_asset})", round(base_value, 4), round(quote_balance, 4)]
        ]
        if to_show_current_pct:
            data.append(["Current %", f"{base_ratio:.1%}", f"{quote_ratio:.1%}"])
        df = pd.DataFrame(data=data)
        return df

    def active_orders_df(self) -> pd.DataFrame:
        market, trading_pair, base_asset, quote_asset = self._market_info
        price = self.get_price()
        active_orders = self.active_orders
        no_sells = len([o for o in active_orders if not o.is_buy and o.client_order_id and
                        not self._hanging_orders_tracker.is_order_id_in_hanging_orders(o.client_order_id)])
        active_orders.sort(key=lambda x: x.price, reverse=True)
        columns = ["Level", "Type", "Price", "Spread", "Amount (Orig)", "Amount (Adj)", "Age"]
        data = []
        lvl_buy, lvl_sell = 0, 0
        for idx in range(0, len(active_orders)):
            order = active_orders[idx]
            is_hanging_order = self._hanging_orders_tracker.is_order_id_in_hanging_orders(order.client_order_id)
            if not is_hanging_order:
                if order.is_buy:
                    level = lvl_buy + 1
                    lvl_buy += 1
                else:
                    level = no_sells - lvl_sell
                    lvl_sell += 1
            spread = 0 if price == 0 else abs(order.price - price) / price
            age = "n/a"
            # // indicates order is a paper order so 'n/a'. For real orders, calculate age.
            if "//" not in order.client_order_id:
                age = pd.Timestamp(int(time.time()) - int(order.client_order_id[-16:]) / 1e6,
                                   unit='s').strftime('%H:%M:%S')
            amount_orig = self._order_amount
            if is_hanging_order:
                amount_orig = float(order.quantity)
                level = "hang"
            data.append([
                level,
                "buy" if order.is_buy else "sell",
                float(order.price),
                f"{spread:.2%}",
                amount_orig,
                float(order.quantity),
                age
            ])

        return pd.DataFrame(data=data, columns=columns)

    def market_status_data_frame(self, market_trading_pair_tuples: List[MarketTradingPairTuple]) -> pd.DataFrame:
        markets_data = []
        markets_columns = ["Exchange", "Market", "Best Bid", "Best Ask", f"MidPrice"]
        markets_columns.append('Reserved Price')
        markets_columns.append('Optimal Spread')
        market_books = [(self._market_info.market, self._market_info.trading_pair)]
        for market, trading_pair in market_books:
            bid_price = market.get_price(trading_pair, False)
            ask_price = market.get_price(trading_pair, True)
            ref_price = self.get_price()
            markets_data.append([
                market.display_name,
                trading_pair,
                float(bid_price),
                float(ask_price),
                float(ref_price),
                round(self._reserved_price, 5),
                round(self._optimal_spread, 5),
            ])
        return pd.DataFrame(data=markets_data, columns=markets_columns).replace(np.nan, '', regex=True)

    def format_status(self) -> str:
        if not self._all_markets_ready:
            return "Market connectors are not ready."
        cdef:
            list lines = []
            list warning_lines = []
        warning_lines.extend(self.network_warning([self._market_info]))

        markets_df = self.market_status_data_frame([self._market_info])
        lines.extend(["", "  Markets:"] + ["    " + line for line in markets_df.to_string(index=False).split("\n")])

        assets_df = map_df_to_str(self.pure_mm_assets_df(True))
        first_col_length = max(*assets_df[0].apply(len))
        df_lines = assets_df.to_string(index=False, header=False,
                                       formatters={0: ("{:<" + str(first_col_length) + "}").format}).split("\n")
        lines.extend(["", "  Assets:"] + ["    " + line for line in df_lines])

        # See if there are any open orders.
        if len(self.active_orders) > 0:
            df = self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        else:
            lines.extend(["", "  No active maker orders."])

        volatility_pct = self._avg_vol.current_value / float(self.get_price()) * 100.0
        if all((self._gamma, self._alpha, self._kappa, not isnan(volatility_pct))):
            lines.extend(["", f"  Strategy parameters:",
                          f"    risk_factor(\u03B3)= {self._gamma:.5E}",
                          f"    order_book_intensity_factor(\u0391)= {self._alpha:.5E}",
                          f"    order_book_depth_factor(\u03BA)= {self._kappa:.5E}",
                          f"    volatility= {volatility_pct:.3f}%"])
            if self._execution_state.time_left is not None:
                lines.extend([f"    time until end of trading cycle = {str(datetime.timedelta(seconds=float(self._execution_state.time_left)//1e3))}"])
            else:
                lines.extend([f"    time until end of trading cycle = N/A"])

        warning_lines.extend(self.balance_warning([self._market_info]))

        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    def execute_orders_proposal(self, proposal: Proposal):
        return self.c_execute_orders_proposal(proposal)

    def cancel_order(self, order_id: str):
        return self.c_cancel_order(self._market_info, order_id)

    cdef c_start(self, Clock clock, double timestamp):
        StrategyBase.c_start(self, clock, timestamp)
        self._last_timestamp = timestamp

        self._hanging_orders_tracker.register_events(self.active_markets)

        if self._hanging_orders_enabled:
            # start tracking any restored limit order
            restored_order_ids = self.c_track_restored_orders(self.market_info)
            for order_id in restored_order_ids:
                order = next(o for o in self.market_info.market.limit_orders if o.client_order_id == order_id)
                if order:
                    self._hanging_orders_tracker.add_order(order)
                    self._hanging_orders_tracker.update_strategy_orders_with_equivalent_orders()

        self._execution_state.time_left = self._execution_state.closing_time

    def start(self, clock: Clock, timestamp: float):
        self.c_start(clock, timestamp)

    cdef c_stop(self, Clock clock):
        self._hanging_orders_tracker.unregister_events(self.active_markets)
        StrategyBase.c_stop(self, clock)

    cdef c_tick(self, double timestamp):
        StrategyBase.c_tick(self, timestamp)
        cdef:
            int64_t current_tick = <int64_t>(timestamp // self._status_report_interval)
            int64_t last_tick = <int64_t>(self._last_timestamp // self._status_report_interval)
            bint should_report_warnings = ((current_tick > last_tick) and
                                           (self._logging_options & self.OPTION_LOG_STATUS_REPORT))
            object proposal

        try:
            if not self._all_markets_ready:
                self._all_markets_ready = all([mkt.ready for mkt in self._sb_markets])
                if not self._all_markets_ready:
                    # Markets not ready yet. Don't do anything.
                    if should_report_warnings:
                        self.logger().warning(f"Markets are not ready. No market making trades are permitted.")
                    return

            if should_report_warnings:
                if not all([mkt.network_status is NetworkStatus.CONNECTED for mkt in self._sb_markets]):
                    self.logger().warning(f"WARNING: Some markets are not connected or are down at the moment. Market "
                                          f"making may be dangerous when markets or networks are unstable.")

            self.c_collect_market_variables(timestamp)
            if self.c_is_algorithm_ready():
                if self._create_timestamp <= self._current_timestamp:
                    # Measure order book liquidity
                    self.c_measure_order_book_liquidity()

                self._hanging_orders_tracker.process_tick()

                # Needs to be executed at all times to not to have active order leftovers after a trading session ends
                self.c_cancel_active_orders_on_max_age_limit()

                self._execution_state.process_tick(timestamp, self)

            else:
                # Only if snapshots are different - for trading intensity - a market order happened
                if self.c_is_algorithm_changed():
                    self._ticks_to_be_ready -= 1
                    if self._ticks_to_be_ready % 5 == 0:
                        self.logger().info(f"Calculating volatility, estimating order book liquidity ... {self._ticks_to_be_ready} ticks to fill buffers")
                else:
                    self.logger().info(f"Calculating volatility, estimating order book liquidity ... no change tick")
        finally:
            self._last_timestamp = timestamp

    def process_tick(self, timestamp: float):
        proposal = None
        if self._create_timestamp <= self._current_timestamp:
            # 1. Calculate reserved price and optimal spread from gamma, alpha, kappa and volatility
            self.c_calculate_reserved_price_and_optimal_spread()
            # 2. Check if calculated prices make sense
            if self._optimal_bid > 0 and self._optimal_ask > 0:
                # 3. Create base order proposals
                proposal = self.c_create_base_proposal()
                # 4. Apply functions that modify orders amount
                self.c_apply_order_amount_eta_transformation(proposal)
                # 5. Apply functions that modify orders price
                self.c_apply_order_price_modifiers(proposal)
                # 6. Apply budget constraint, i.e. can't buy/sell more than what you have.
                self.c_apply_budget_constraint(proposal)

                self.c_cancel_active_orders(proposal)

        if self.c_to_create_orders(proposal):
            self.c_execute_orders_proposal(proposal)

        if self._is_debug:
            self.dump_debug_variables()

    cdef c_collect_market_variables(self, double timestamp):
        market, trading_pair, base_asset, quote_asset = self._market_info
        self._last_sampling_timestamp = timestamp

        price = self.get_price()
        snapshot = self.get_order_book_snapshot()
        self._avg_vol.add_sample(price)
        self._trading_intensity.add_sample(snapshot)
        # Calculate adjustment factor to have 0.01% of inventory resolution
        base_balance = market.get_balance(base_asset)
        quote_balance = market.get_balance(quote_asset)
        inventory_in_base = quote_balance / price + base_balance

    def collect_market_variables(self, timestamp: float):
        self.c_collect_market_variables(timestamp)

    cdef double c_get_spread(self):
        cdef:
            ExchangeBase market = self._market_info.market
            str trading_pair = self._market_info.trading_pair

        return market.c_get_price(trading_pair, True) - market.c_get_price(trading_pair, False)

    def get_spread(self):
        return self.c_get_spread()

    def get_volatility(self):
        vol = Decimal(str(self._avg_vol.current_value))
        if vol == s_decimal_zero:
            if self._latest_parameter_calculation_vol != s_decimal_zero:
                vol = Decimal(str(self._latest_parameter_calculation_vol))
            else:
                # Default value at start time if price has no activity
                vol = Decimal(str(self.c_get_spread() / 2))
        return vol

    cdef c_measure_order_book_liquidity(self):

        self._alpha, self._kappa = self._trading_intensity.current_value

        self._alpha = Decimal(self._alpha)
        self._kappa = Decimal(self._kappa)

        if self._is_debug:
            self.logger().info(f"alpha={self._alpha:.4f} | "
                               f"kappa={self._kappa:.4f}")

    def measure_order_book_liquidity(self):
        return self.c_measure_order_book_liquidity()

    cdef c_calculate_reserved_price_and_optimal_spread(self):
        cdef:
            ExchangeBase market = self._market_info.market

        # Current mid price
        price = self.get_price()

        # The amount of stocks owned - q - has to be in relative units, not absolute, because changing the portfolio size shouldn't change the reserved price
        # The reserved price should concern itself only with the strategy performance, i.e. amount of stocks relative to the target
        inventory = Decimal(str(self.c_calculate_inventory()))

        if inventory == 0:
            return

        q_target = Decimal(str(self.c_calculate_target_inventory()))
        q = (market.get_balance(self.base_asset) - q_target) / (inventory)
        # Volatility has to be in absolute values (prices) because in calculation of reserved price it's not multiplied by the current price, therefore
        # it can't be a percentage. The result of the multiplication has to be an absolute price value because it's being subtracted from the current price
        vol = self.get_volatility()
        mid_price_variance = vol ** 2

        # order book liquidity - kappa and alpha have to represent absolute values because the second member of the optimal spread equation has to be an absolute price
        # and from the reserved price calculation we know that gamma's unit is not absolute price
        if all((self._gamma, self._kappa)) and self._alpha != 0 and self._kappa > 0 and vol != 0:
            if self._execution_state.time_left is not None and self._execution_state.closing_time is not None:
                # Avellaneda-Stoikov for a fixed timespan
                time_left_fraction = Decimal(str(self._execution_state.time_left / self._execution_state.closing_time))

                self._reserved_price = price - (q * self._gamma * mid_price_variance * time_left_fraction)

                self._optimal_spread = self._gamma * mid_price_variance * time_left_fraction
                self._optimal_spread += 2 * Decimal(1 + self._gamma / self._kappa).ln() / self._gamma
            else:
                # Avellaneda-Stoikov for an infinite timespan
                # gamma reversed to achieve unit consistency as for finite timeframe
                q_max = 1
                omega = Decimal(1 / 2) * ((1 / self._gamma) ** 2) * (vol ** 2) * Decimal((q_max + 1) ** 2)
                offset_ask = Decimal(self._gamma) * Decimal(1 + ((1 - 2 * q) * ((1 / self._gamma) ** 2) * (vol ** 2)) / (2 * omega - (((1 / self._gamma) ** 2) * (q ** 2) * (vol ** 2)))).ln()
                offset_bid = Decimal(self._gamma) * Decimal(1 + ((-1 - 2 * q) * ((1 / self._gamma) ** 2) * (vol ** 2)) / (2 * omega - (((1 / self._gamma) ** 2) * (q ** 2) * (vol ** 2)))).ln()
                reserved_price_ask = price + offset_ask
                reserved_price_bid = price + offset_bid
                self._reserved_price = (reserved_price_ask + reserved_price_bid) / 2

                # Derived from the asymptotic expansion in q for finite timeframe
                self._optimal_spread = -(offset_ask + offset_bid) / (2 * q)
                self._optimal_spread += 2 * Decimal(1 + self._gamma / self._kappa).ln() / self._gamma

            min_spread = price / 100 * Decimal(str(self._min_spread))

            max_limit_bid = price - min_spread / 2
            min_limit_ask = price + min_spread / 2

            self._optimal_ask = max(self._reserved_price + self._optimal_spread / 2, min_limit_ask)
            self._optimal_bid = min(self._reserved_price - self._optimal_spread / 2, max_limit_bid)

            # This is not what the algorithm will use as proposed bid and ask. This is just the raw output.
            # Optimal bid and optimal ask prices will be used
            if self._is_debug:
                self.logger().info(f"q={q:.4f} | "
                                   f"vol={vol:.10f}")
                self.logger().info(f"mid_price={price:.10f} | "
                                   f"reserved_price={self._reserved_price:.10f} | "
                                   f"optimal_spread={self._optimal_spread:.10f}")
                self.logger().info(f"optimal_bid={(price-(self._reserved_price - self._optimal_spread / 2)) / price * 100:.4f}% | "
                                   f"optimal_ask={((self._reserved_price + self._optimal_spread / 2) - price) / price * 100:.4f}%")

    def calculate_reserved_price_and_optimal_spread(self):
        return self.c_calculate_reserved_price_and_optimal_spread()

    cdef object c_calculate_target_inventory(self):
        cdef:
            ExchangeBase market = self._market_info.market
            str trading_pair = self._market_info.trading_pair
            str base_asset = self._market_info.base_asset
            str quote_asset = self._market_info.quote_asset
            object mid_price
            object base_value
            object inventory_value
            object target_inventory_value

        price = self.get_price()
        base_asset_amount = market.get_balance(base_asset)
        quote_asset_amount = market.get_balance(quote_asset)
        # Base asset value in quote asset prices
        base_value = base_asset_amount * price
        # Total inventory value in quote asset prices
        inventory_value = base_value + quote_asset_amount
        # Target base asset value in quote asset prices
        target_inventory_value = inventory_value * self._inventory_target_base_pct
        # Target base asset amount
        target_inventory_amount = target_inventory_value / price
        return market.c_quantize_order_amount(trading_pair, Decimal(str(target_inventory_amount)))

    def calculate_target_inventory(self) -> Decimal:
        return self.c_calculate_target_inventory()

    cdef c_calculate_inventory(self):
        cdef:
            ExchangeBase market = self._market_info.market
            str base_asset = self._market_info.base_asset
            str quote_asset = self._market_info.quote_asset
            object mid_price
            object base_value
            object inventory_value
            object inventory_value_quote
            object inventory_value_base

        price = self.get_price()
        base_asset_amount = market.get_balance(base_asset)
        quote_asset_amount = market.get_balance(quote_asset)
        # Base asset value in quote asset prices
        base_value = base_asset_amount * price
        # Total inventory value in quote asset prices
        inventory_value_quote = base_value + quote_asset_amount
        # Total inventory value in base asset prices
        inventory_value_base = inventory_value_quote / price
        return inventory_value_base

    def calculate_inventory(self) -> Decimal:
        return self.c_calculate_inventory()

    cdef bint c_is_algorithm_ready(self):
        return self._avg_vol.is_sampling_buffer_full and self._trading_intensity.is_sampling_buffer_full

    cdef bint c_is_algorithm_changed(self):
        return self._trading_intensity.is_sampling_buffer_changed

    def is_algorithm_ready(self) -> bool:
        return self.c_is_algorithm_ready()

    def is_algorithm_changed(self) -> bool:
        return self.c_is_algorithm_changed()

    def _get_level_spreads(self):
        level_step = ((self._optimal_spread / 2) / 100) * self._level_distances

        bid_level_spreads = [i * level_step for i in range(self._order_levels)]
        ask_level_spreads = [i * level_step for i in range(self._order_levels)]

        return bid_level_spreads, ask_level_spreads

    cdef _create_proposal_based_on_order_override(self):
        cdef:
            ExchangeBase market = self._market_info.market
            list buys = []
            list sells = []
        reference_price = self.get_price()
        for key, value in self._order_override.items():
            if str(value[0]) in ["buy", "sell"]:
                list_to_be_appended = buys if str(value[0]) == "buy" else sells
                size = Decimal(str(value[2]))
                size = market.c_quantize_order_amount(self.trading_pair, size)
                if str(value[0]) == "buy":
                    price = reference_price * (Decimal("1") - Decimal(str(value[1])) / Decimal("100"))
                elif str(value[0]) == "sell":
                    price = reference_price * (Decimal("1") + Decimal(str(value[1])) / Decimal("100"))
                price = market.c_quantize_order_price(self.trading_pair, price)
                if size > 0 and price > 0:
                    list_to_be_appended.append(PriceSize(price, size))
        return buys, sells

    def create_proposal_based_on_order_override(self) -> Tuple[List[Proposal], List[Proposal]]:
        return self._create_proposal_based_on_order_override()

    cdef _create_proposal_based_on_order_levels(self):
        cdef:
            ExchangeBase market = self._market_info.market
            list buys = []
            list sells = []
        bid_level_spreads, ask_level_spreads = self._get_level_spreads()
        size = market.c_quantize_order_amount(self.trading_pair, self._order_amount)
        if size > 0:
            for level in range(self._order_levels):
                bid_price = market.c_quantize_order_price(self.trading_pair,
                                                          self._optimal_bid - Decimal(str(bid_level_spreads[level])))
                ask_price = market.c_quantize_order_price(self.trading_pair,
                                                          self._optimal_ask + Decimal(str(ask_level_spreads[level])))

                buys.append(PriceSize(bid_price, size))
                sells.append(PriceSize(ask_price, size))
        return buys, sells

    def create_proposal_based_on_order_levels(self):
        return self._create_proposal_based_on_order_levels()

    cdef _create_basic_proposal(self):
        cdef:
            ExchangeBase market = self._market_info.market
            list buys = []
            list sells = []
        price = market.c_quantize_order_price(self.trading_pair, Decimal(str(self._optimal_bid)))
        size = market.c_quantize_order_amount(self.trading_pair, self._order_amount)
        if size > 0:
            buys.append(PriceSize(price, size))

        price = market.c_quantize_order_price(self.trading_pair, Decimal(str(self._optimal_ask)))
        size = market.c_quantize_order_amount(self.trading_pair, self._order_amount)
        if size > 0:
            sells.append(PriceSize(price, size))
        return buys, sells

    def create_basic_proposal(self):
        return self._create_basic_proposal()

    cdef object c_create_base_proposal(self):
        cdef:
            ExchangeBase market = self._market_info.market
            list buys = []
            list sells = []

        if self._order_override is not None and len(self._order_override) > 0:
            # If order_override is set, it will override order_levels
            buys, sells = self._create_proposal_based_on_order_override()
        elif self._order_levels > 0:
            # Simple order levels
            buys, sells = self._create_proposal_based_on_order_levels()
        else:
            # No order levels nor order_overrides. Just 1 bid and 1 ask order
            buys, sells = self._create_basic_proposal()

        return Proposal(buys, sells)

    def create_base_proposal(self):
        return self.c_create_base_proposal()

    cdef tuple c_get_adjusted_available_balance(self, list orders):
        """
        Calculates the available balance, plus the amount attributed to orders.
        :return: (base amount, quote amount) in Decimal
        """
        cdef:
            ExchangeBase market = self._market_info.market
            object base_balance = market.c_get_available_balance(self.base_asset)
            object quote_balance = market.c_get_available_balance(self.quote_asset)

        for order in orders:
            if order.is_buy:
                quote_balance += order.quantity * order.price
            else:
                base_balance += order.quantity

        return base_balance, quote_balance

    def get_adjusted_available_balance(self, orders: List[LimitOrder]):
        return self.c_get_adjusted_available_balance(orders)

    cdef c_apply_order_price_modifiers(self, object proposal):
        if self._order_optimization_enabled:
            self.c_apply_order_optimization(proposal)

        if self._add_transaction_costs_to_orders:
            self.c_apply_add_transaction_costs(proposal)

    def apply_order_price_modifiers(self, proposal: Proposal):
        self.c_apply_order_price_modifiers(proposal)

    def apply_budget_constraint(self, proposal: Proposal):
        return self.c_apply_budget_constraint(proposal)

    def adjusted_available_balance_for_orders_budget_constrain(self):
        candidate_hanging_orders = self.hanging_orders_tracker.candidate_hanging_orders_from_pairs()
        non_hanging = []
        if self.market_info in self._sb_order_tracker.get_limit_orders():
            all_orders = self._sb_order_tracker.get_limit_orders()[self.market_info].values()
            non_hanging = [order for order in all_orders
                           if not self._hanging_orders_tracker.is_order_id_in_hanging_orders(order.client_order_id)]
        all_non_hanging_orders = list(set(non_hanging) - set(candidate_hanging_orders))
        return self.c_get_adjusted_available_balance(all_non_hanging_orders)

    cdef c_apply_budget_constraint(self, object proposal):
        cdef:
            ExchangeBase market = self._market_info.market
            object quote_size
            object base_size
            object adjusted_amount

        base_balance, quote_balance = self.adjusted_available_balance_for_orders_budget_constrain()

        for buy in proposal.buys:
            buy_fee = market.c_get_fee(self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.BUY,
                                       buy.size, buy.price)
            quote_size = buy.size * buy.price * (Decimal(1) + buy_fee.percent)

            # Adjust buy order size to use remaining balance if less than the order amount
            if quote_balance < quote_size:
                adjusted_amount = quote_balance / (buy.price * (Decimal("1") + buy_fee.percent))
                adjusted_amount = market.c_quantize_order_amount(self.trading_pair, adjusted_amount)
                buy.size = adjusted_amount
                quote_balance = s_decimal_zero
            elif quote_balance == s_decimal_zero:
                buy.size = s_decimal_zero
            else:
                quote_balance -= quote_size

        proposal.buys = [o for o in proposal.buys if o.size > 0]

        for sell in proposal.sells:
            base_size = sell.size

            # Adjust sell order size to use remaining balance if less than the order amount
            if base_balance < base_size:
                adjusted_amount = market.c_quantize_order_amount(self.trading_pair, base_balance)
                sell.size = adjusted_amount
                base_balance = s_decimal_zero
            elif base_balance == s_decimal_zero:
                sell.size = s_decimal_zero
            else:
                base_balance -= base_size

        proposal.sells = [o for o in proposal.sells if o.size > 0]

    def apply_budget_constraint(self, proposal: Proposal):
        return self.c_apply_budget_constraint(proposal)

    # Compare the market price with the top bid and top ask price
    cdef c_apply_order_optimization(self, object proposal):
        cdef:
            ExchangeBase market = self._market_info.market
            object own_buy_size = s_decimal_zero
            object own_sell_size = s_decimal_zero
            object best_order_spread

        for order in self.active_orders:
            if order.is_buy:
                own_buy_size = order.quantity
            else:
                own_sell_size = order.quantity

        if len(proposal.buys) > 0:
            # Get the top bid price in the market using order_optimization_depth and your buy order volume
            top_bid_price = self._market_info.get_price_for_volume(
                False, own_buy_size).result_price
            price_quantum = market.c_get_order_price_quantum(
                self.trading_pair,
                top_bid_price
            )
            # Get the price above the top bid
            price_above_bid = (ceil(top_bid_price / price_quantum) + 1) * price_quantum

            # If the price_above_bid is lower than the price suggested by the top pricing proposal,
            # lower the price and from there apply the best_order_spread to each order in the next levels
            proposal.buys = sorted(proposal.buys, key = lambda p: p.price, reverse = True)
            for i, proposed in enumerate(proposal.buys):
                if proposal.buys[i].price > price_above_bid:
                    proposal.buys[i].price = market.c_quantize_order_price(self.trading_pair, price_above_bid)

        if len(proposal.sells) > 0:
            # Get the top ask price in the market using order_optimization_depth and your sell order volume
            top_ask_price = self._market_info.get_price_for_volume(
                True, own_sell_size).result_price
            price_quantum = market.c_get_order_price_quantum(
                self.trading_pair,
                top_ask_price
            )
            # Get the price below the top ask
            price_below_ask = (floor(top_ask_price / price_quantum) - 1) * price_quantum

            # If the price_below_ask is higher than the price suggested by the pricing proposal,
            # increase your price and from there apply the best_order_spread to each order in the next levels
            proposal.sells = sorted(proposal.sells, key = lambda p: p.price)
            for i, proposed in enumerate(proposal.sells):
                if proposal.sells[i].price < price_below_ask:
                    proposal.sells[i].price = market.c_quantize_order_price(self.trading_pair, price_below_ask)

    def apply_order_optimization(self, proposal: Proposal):
        return self.c_apply_order_optimization(proposal)

    cdef c_apply_order_amount_eta_transformation(self, object proposal):
        cdef:
            ExchangeBase market = self._market_info.market
            str trading_pair = self._market_info.trading_pair

        # Order amounts should be changed only if order_override is not active
        if (self._order_override is None) or (len(self._order_override) == 0):
            # eta parameter is described in the paper as the shape parameter for having exponentially decreasing order amount
            # for orders that go against inventory target (i.e. Want to buy when excess inventory or sell when deficit inventory)

            # q cannot be in absolute values - cannot be dependent on the size of the inventory or amount of base asset
            # because it's a scaling factor
            inventory = Decimal(str(self.c_calculate_inventory()))

            if inventory == 0:
                return

            q_target = Decimal(str(self.c_calculate_target_inventory()))
            q = (market.get_balance(self.base_asset) - q_target) / (inventory)

            if len(proposal.buys) > 0:
                if q > 0:
                    for i, proposed in enumerate(proposal.buys):

                        proposal.buys[i].size = market.c_quantize_order_amount(trading_pair, proposal.buys[i].size * Decimal.exp(-self._eta * q))
                    proposal.buys = [o for o in proposal.buys if o.size > 0]

            if len(proposal.sells) > 0:
                if q < 0:
                    for i, proposed in enumerate(proposal.sells):
                        proposal.sells[i].size = market.c_quantize_order_amount(trading_pair, proposal.sells[i].size * Decimal.exp(self._eta * q))
                    proposal.sells = [o for o in proposal.sells if o.size > 0]

    def apply_order_amount_eta_transformation(self, proposal: Proposal):
        self.c_apply_order_amount_eta_transformation(proposal)

    cdef c_apply_add_transaction_costs(self, object proposal):
        cdef:
            ExchangeBase market = self._market_info.market
        for buy in proposal.buys:
            fee = market.c_get_fee(self.base_asset, self.quote_asset,
                                   self._limit_order_type, TradeType.BUY, buy.size, buy.price)
            price = buy.price * (Decimal(1) - fee.percent)
            buy.price = market.c_quantize_order_price(self.trading_pair, price)
        for sell in proposal.sells:
            fee = market.c_get_fee(self.base_asset, self.quote_asset,
                                   self._limit_order_type, TradeType.SELL, sell.size, sell.price)
            price = sell.price * (Decimal(1) + fee.percent)
            sell.price = market.c_quantize_order_price(self.trading_pair, price)

    def apply_add_transaction_costs(self, proposal: Proposal):
        self.c_apply_add_transaction_costs(proposal)

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
        self.c_did_complete_order(order_completed_event)

    cdef c_did_complete_sell_order(self, object order_completed_event):
        self.c_did_complete_order(order_completed_event)

    cdef c_did_complete_order(self, object order_completed_event):
        cdef:
            str order_id = order_completed_event.order_id
            LimitOrder limit_order_record = self._sb_order_tracker.c_get_limit_order(self._market_info, order_id)

        if limit_order_record is None:
            return

        # Continue only if the order is not a hanging order
        if (not self._hanging_orders_tracker.is_order_id_in_hanging_orders(order_id)
                and not self.hanging_orders_tracker.is_order_id_in_completed_hanging_orders(order_id)):
            # delay order creation by filled_order_delay (in seconds)
            self._create_timestamp = self._current_timestamp + self._filled_order_delay
            self._cancel_timestamp = min(self._cancel_timestamp, self._create_timestamp)

            if limit_order_record.is_buy:
                self._filled_buys_balance += 1
                order_action_string = "buy"
            else:
                self._filled_sells_balance += 1
                order_action_string = "sell"

            self._last_own_trade_price = limit_order_record.price

            self.log_with_clock(
                logging.INFO,
                f"({self.trading_pair}) Maker {order_action_string} order {order_id} "
                f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
            )
            self.notify_hb_app_with_timestamp(
                f"Maker {order_action_string.upper()} order "
                f"{limit_order_record.quantity} {limit_order_record.base_currency} @ "
                f"{limit_order_record.price} {limit_order_record.quote_currency} is filled."
            )

    cdef bint c_is_within_tolerance(self, list current_prices, list proposal_prices):
        if len(current_prices) != len(proposal_prices):
            return False
        current_prices = sorted(current_prices)
        proposal_prices = sorted(proposal_prices)
        for current, proposal in zip(current_prices, proposal_prices):
            # if spread diff is more than the tolerance or order quantities are different, return false.
            if abs(proposal - current) / current > self._order_refresh_tolerance_pct:
                return False
        return True

    def is_within_tolerance(self, current_prices: List[Decimal], proposal_prices: List[Decimal]) -> bool:
        return self.c_is_within_tolerance(current_prices, proposal_prices)

    cdef c_cancel_active_orders_on_max_age_limit(self):
        """
        Cancels active non hanging orders if they are older than max age limit
        """
        cdef:
            list active_orders = self.active_non_hanging_orders
        for order in active_orders:
            if order_age(order) > self._max_order_age:
                self.c_cancel_order(self._market_info, order.client_order_id)

    cdef c_cancel_active_orders(self, object proposal):
        if self._cancel_timestamp > self._current_timestamp:
            return

        cdef:
            list active_buy_prices = []
            list active_sells = []
            bint to_defer_canceling = False
        if len(self.active_non_hanging_orders) == 0:
            return
        if proposal is not None:
            active_buy_prices = [Decimal(str(o.price)) for o in self.active_non_hanging_orders if o.is_buy]
            active_sell_prices = [Decimal(str(o.price)) for o in self.active_non_hanging_orders if not o.is_buy]
            proposal_buys = [buy.price for buy in proposal.buys]
            proposal_sells = [sell.price for sell in proposal.sells]

            if self.c_is_within_tolerance(active_buy_prices, proposal_buys) and \
                    self.c_is_within_tolerance(active_sell_prices, proposal_sells):
                to_defer_canceling = True

        if not to_defer_canceling:
            self._hanging_orders_tracker.update_strategy_orders_with_equivalent_orders()
            for order in self.active_non_hanging_orders:
                # If is about to be added to hanging_orders then don't cancel
                if not self._hanging_orders_tracker.is_potential_hanging_order(order):
                    self.c_cancel_order(self._market_info, order.client_order_id)
        else:
            self.c_set_timers()

    def cancel_active_orders(self, proposal: Proposal):
        return self.c_cancel_active_orders(proposal)

    cdef bint c_to_create_orders(self, object proposal):
        non_hanging_orders_non_cancelled = [o for o in self.active_non_hanging_orders if not
                                            self._hanging_orders_tracker.is_potential_hanging_order(o)]

        return (self._create_timestamp < self._current_timestamp
                and (not self._should_wait_order_cancel_confirmation or
                     len(self._sb_order_tracker.in_flight_cancels) == 0)
                and proposal is not None
                and len(non_hanging_orders_non_cancelled) == 0)

    def to_create_orders(self, proposal: Proposal) -> bool:
        return self.c_to_create_orders(proposal)

    cdef c_execute_orders_proposal(self, object proposal):
        cdef:
            double expiration_seconds = NaN
            str bid_order_id, ask_order_id
            bint orders_created = False
        # Number of pair of orders to track for hanging orders
        number_of_pairs = min((len(proposal.buys), len(proposal.sells))) if self._hanging_orders_enabled else 0

        if len(proposal.buys) > 0:
            if self._logging_options & self.OPTION_LOG_CREATE_ORDER:
                price_quote_str = [f"{buy.size.normalize()} {self.base_asset}, "
                                   f"{buy.price.normalize()} {self.quote_asset}"
                                   for buy in proposal.buys]
                self.logger().info(
                    f"({self.trading_pair}) Creating {len(proposal.buys)} bid orders "
                    f"at (Size, Price): {price_quote_str}"
                )
            for idx, buy in enumerate(proposal.buys):
                bid_order_id = self.c_buy_with_specific_market(
                    self._market_info,
                    buy.size,
                    order_type=self._limit_order_type,
                    price=buy.price,
                    expiration_seconds=expiration_seconds
                )
                orders_created = True
                if idx < number_of_pairs:
                    order = next((o for o in self.active_orders if o.client_order_id == bid_order_id))
                    if order:
                        self._hanging_orders_tracker.add_current_pairs_of_proposal_orders_executed_by_strategy(
                            CreatedPairOfOrders(order, None))
        if len(proposal.sells) > 0:
            if self._logging_options & self.OPTION_LOG_CREATE_ORDER:
                price_quote_str = [f"{sell.size.normalize()} {self.base_asset}, "
                                   f"{sell.price.normalize()} {self.quote_asset}"
                                   for sell in proposal.sells]
                self.logger().info(
                    f"({self.trading_pair}) Creating {len(proposal.sells)} ask "
                    f"orders at (Size, Price): {price_quote_str}"
                )
            for idx, sell in enumerate(proposal.sells):
                ask_order_id = self.c_sell_with_specific_market(
                    self._market_info,
                    sell.size,
                    order_type=self._limit_order_type,
                    price=sell.price,
                    expiration_seconds=expiration_seconds
                )
                orders_created = True
                if idx < number_of_pairs:
                    order = next((o for o in self.active_orders if o.client_order_id == ask_order_id))
                    if order:
                        self._hanging_orders_tracker.current_created_pairs_of_orders[idx].sell_order = order
        if orders_created:
            self.c_set_timers()

    def execute_orders_proposal(self, proposal: Proposal):
        self.c_execute_orders_proposal(proposal)

    cdef c_set_timers(self):
        cdef double next_cycle = self._current_timestamp + self._order_refresh_time
        if self._create_timestamp <= self._current_timestamp:
            self._create_timestamp = next_cycle
        if self._cancel_timestamp <= self._current_timestamp:
            self._cancel_timestamp = min(self._create_timestamp, next_cycle)

    def set_timers(self):
        self.c_set_timers()

    def notify_hb_app(self, msg: str):
        if self._hb_app_notification:
            super().notify_hb_app(msg)

    def dump_debug_variables(self):
        market = self._market_info.market
        mid_price = self.get_price()
        spread = Decimal(str(self.c_get_spread()))

        best_ask = mid_price + spread / 2
        new_ask = self._reserved_price + self._optimal_spread / 2
        best_bid = mid_price - spread / 2
        new_bid = self._reserved_price - self._optimal_spread / 2

        vol = self.get_volatility()
        mid_price_variance = vol ** 2

        if not os.path.exists(self._debug_csv_path):
            df_header = pd.DataFrame([('mid_price',
                                       'best_bid',
                                       'best_ask',
                                       'reserved_price',
                                       'optimal_spread',
                                       'optimal_bid',
                                       'optimal_ask',
                                       'optimal_bid_to_mid_%',
                                       'optimal_ask_to_mid_%',
                                       'current_inv',
                                       'target_inv',
                                       'time_left_fraction',
                                       'mid_price std_dev',
                                       'gamma',
                                       'alpha',
                                       'kappa',
                                       'eta',
                                       'volatility',
                                       'mid_price_variance',
                                       'inventory_target_pct')])
            df_header.to_csv(self._debug_csv_path, mode='a', header=False, index=False)

        if self._execution_state.time_left is not None and self._execution_state.closing_time is not None:
            time_left_fraction = self._execution_state.time_left / self._execution_state.closing_time
        else:
            time_left_fraction = None

        df = pd.DataFrame([(mid_price,
                            best_bid,
                            best_ask,
                            self._reserved_price,
                            self._optimal_spread,
                            self._optimal_bid,
                            self._optimal_ask,
                            (mid_price - (self._reserved_price - self._optimal_spread / 2)) / mid_price,
                            ((self._reserved_price + self._optimal_spread / 2) - mid_price) / mid_price,
                            market.get_balance(self.base_asset),
                            self.c_calculate_target_inventory(),
                            time_left_fraction,
                            self._avg_vol.current_value,
                            self._gamma,
                            self._alpha,
                            self._kappa,
                            self._eta,
                            vol,
                            mid_price_variance,
                            self.inventory_target_base_pct)])
        df.to_csv(self._debug_csv_path, mode='a', header=False, index=False)
