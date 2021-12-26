# distutils: language=c++
from decimal import Decimal
import logging

import os.path
import pandas as pd
import numpy as np
from typing import (
    List,
    Dict,
    Optional
)
from math import (
    floor,
    ceil
)
import time
from hummingbot.core.clock cimport Clock
from hummingbot.core.event.events import TradeType, PriceType
from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.event.events import OrderType

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_base import StrategyBase
from hummingbot.client.config.global_config_map import global_config_map

from .data_types import (
    Proposal,
    PriceSize
)
from .aroon_oscillator_order_tracker import AroonOscillatorOrderTracker

from hummingbot.strategy.pure_market_making.inventory_skew_calculator cimport c_calculate_bid_ask_ratios_from_base_asset_ratio
from hummingbot.strategy.pure_market_making.inventory_skew_calculator import calculate_total_order_size
from .aroon_oscillator_indicator cimport AroonOscillatorIndicator, OscillatorPeriod
from .aroon_oscillator_indicator import AroonOscillatorIndicator, OscillatorPeriod


NaN = float("nan")
s_decimal_zero = Decimal(0)
s_decimal_neg_one = Decimal(-1)
s_decimal_one_oh = Decimal("1.0")
s_decimal_one_hundo = Decimal("100")
pmm_logger = None

# AroonOscillatorStrategy is a market making strategy that uses Aroon Indicators to detect trends
# A user will set up the number of periods in the Indicator and how long each period is in seconds.
# The user also sets a minimum and maximum spread that they desire. Then the indicator will use the
# collected period data to automatically adjust the spreads to try and position orders at the best
# spot for profitable trades.
# Traditionally the number of periods is 25, but any amount can be used. Lower numbers will produce
# more oscillations, which in turn will adjust the spreads more drastically. Higher numbers will produce
# less oscillations, this will adjust the spreads more smoothly.
# The time duration of the period can be chosen to best suit your trade strategy. For example if you use
# 5 minute candles when analysing market data, set the duration to 300 seconds.
# minimum_periods can be set to have the indicator engage adjusting the spreads before the Indicator
# periods fill up. Set this to -1 to have only adjust spreads when the indicator is full.
# The strategy will adjust the bid_spread closer to minimum_spread the closer Aroon Down indicator gets
# closer to 100, and it will adjust the ask_spread closer to the minimum_spread the closer Aroon Up gets
# closer to 100. The spread is further adjusted by the Aroon Oscillator indicator. If the indicator strongly
# suggests a trend, it will push the spread out further from minimum_spread in order to wait for a more optimal
# point to trade. The affect of the oscillator indicator can be adjusted by the aroon_osc_strength_factor parameter
# a setting lower than 1.0 will decrease its effect on the spread during a strong trend.
# The rest of the strategy is pretty much copied from PureMarketMakingStrategy. A few options have been removed
# such at the pricing delegates. There are more features that could possibly be removed, since they don't work
# well with the Indicator.

cdef class AroonOscillatorStrategy(StrategyBase):
    OPTION_LOG_CREATE_ORDER = 1 << 3
    OPTION_LOG_MAKER_ORDER_FILLED = 1 << 4
    OPTION_LOG_STATUS_REPORT = 1 << 5
    OPTION_LOG_ALL = 0x7fffffffffffffff

    # These are exchanges where you're expected to expire orders instead of actively cancelling them.
    RADAR_RELAY_TYPE_EXCHANGES = {"radar_relay", "bamboo_relay"}

    @classmethod
    def logger(cls):
        global pmm_logger
        if pmm_logger is None:
            pmm_logger = logging.getLogger(__name__)
        return pmm_logger

    def __init__(self,
                 market_info: MarketTradingPairTuple,
                 minimum_spread: Decimal,
                 maximum_spread: Decimal,
                 period_length: int,
                 period_duration: int,
                 order_amount: Decimal,
                 order_levels: int = 1,
                 minimum_periods: int = -1,
                 aroon_osc_strength_factor: Decimal = Decimal("0.5"),
                 order_level_spread: Decimal = s_decimal_zero,
                 order_level_amount: Decimal = s_decimal_zero,
                 order_refresh_time: float = 30.0,
                 max_order_age = 1800.0,
                 order_refresh_tolerance_pct: Decimal = s_decimal_neg_one,
                 cancel_order_spread_threshold: Decimal = s_decimal_zero,
                 filled_order_delay: float = 60.0,
                 inventory_skew_enabled: bool = False,
                 inventory_target_base_pct: Decimal = s_decimal_zero,
                 inventory_range_multiplier: Decimal = s_decimal_zero,
                 hanging_orders_enabled: bool = False,
                 hanging_orders_cancel_pct: Decimal = Decimal("0.1"),
                 order_optimization_enabled: bool = False,
                 ask_order_optimization_depth: Decimal = s_decimal_zero,
                 bid_order_optimization_depth: Decimal = s_decimal_zero,
                 add_transaction_costs_to_orders: bool = False,
                 price_type: str = "mid_price",
                 take_if_crossed: bool = False,
                 price_ceiling: Decimal = s_decimal_neg_one,
                 price_floor: Decimal = s_decimal_neg_one,
                 logging_options: int = OPTION_LOG_ALL,
                 status_report_interval: float = 900,
                 hb_app_notification: bool = False,
                 order_override: Dict[str, List[str]] = {},
                 debug_csv_path: str = '',
                 is_debug: bool = True,
                 ):

        if price_ceiling != s_decimal_neg_one and price_ceiling < price_floor:
            raise ValueError("Parameter price_ceiling cannot be lower than price_floor.")

        super().__init__()
        self._sb_order_tracker = AroonOscillatorOrderTracker()
        self._market_info = market_info
        self._bid_spread = s_decimal_zero
        self._ask_spread = s_decimal_zero
        self._minimum_spread = minimum_spread
        self._maximum_spread = maximum_spread
        self._minimum_periods = minimum_periods
        self._aroon_osc_strength_factor = aroon_osc_strength_factor
        self._order_amount = order_amount
        self._order_levels = order_levels
        self._buy_levels = order_levels
        self._sell_levels = order_levels
        self._order_level_spread = order_level_spread
        self._order_level_amount = order_level_amount
        self._order_refresh_time = order_refresh_time
        self._max_order_age = max_order_age
        self._order_refresh_tolerance_pct = order_refresh_tolerance_pct
        self._filled_order_delay = filled_order_delay
        self._inventory_skew_enabled = inventory_skew_enabled
        self._inventory_target_base_pct = inventory_target_base_pct
        self._inventory_range_multiplier = inventory_range_multiplier
        self._hanging_orders_enabled = hanging_orders_enabled
        self._hanging_orders_cancel_pct = hanging_orders_cancel_pct
        self._order_optimization_enabled = order_optimization_enabled
        self._ask_order_optimization_depth = ask_order_optimization_depth
        self._bid_order_optimization_depth = bid_order_optimization_depth
        self._add_transaction_costs_to_orders = add_transaction_costs_to_orders
        self._price_type = self.get_price_type(price_type)
        self._take_if_crossed = take_if_crossed
        self._price_ceiling = price_ceiling
        self._price_floor = price_floor
        self._hb_app_notification = hb_app_notification
        self._order_override = order_override
        self._period_length = period_length
        self._period_duration = period_duration
        self._cancel_order_spread_threshold = cancel_order_spread_threshold

        self._cancel_timestamp = 0
        self._create_timestamp = 0
        self._hanging_aged_order_prices = []
        self._limit_order_type = self._market_info.market.get_maker_order_type()
        if take_if_crossed:
            self._limit_order_type = OrderType.LIMIT
        self._all_markets_ready = False
        self._filled_buys_balance = 0
        self._filled_sells_balance = 0
        self._hanging_order_ids = []
        self._logging_options = logging_options
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self._last_own_trade_price = Decimal('nan')
        self._aroon_osc = AroonOscillatorIndicator(self._period_length, self._period_duration)
        self._trend_factor = s_decimal_zero
        self._min_max_spread_diff = s_decimal_zero
        self._ask_increase = s_decimal_zero
        self._bid_increase = s_decimal_zero
        self._debug_csv_path = debug_csv_path
        self._is_debug = is_debug

        self.c_add_markets([market_info.market])

    def all_markets_ready(self):
        return all([market.ready for market in self._sb_markets])

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
    def order_levels(self) -> int:
        return self._order_levels

    @order_levels.setter
    def order_levels(self, value: int):
        self._order_levels = value
        self._buy_levels = value
        self._sell_levels = value

    @property
    def buy_levels(self) -> int:
        return self._buy_levels

    @buy_levels.setter
    def buy_levels(self, value: int):
        self._buy_levels = value

    @property
    def sell_levels(self) -> int:
        return self._sell_levels

    @sell_levels.setter
    def sell_levels(self, value: int):
        self._sell_levels = value

    @property
    def order_level_amount(self) -> Decimal:
        return self._order_level_amount

    @order_level_amount.setter
    def order_level_amount(self, value: Decimal):
        self._order_level_amount = value

    @property
    def order_level_spread(self) -> Decimal:
        return self._order_level_spread

    @order_level_spread.setter
    def order_level_spread(self, value: Decimal):
        self._order_level_spread = value

    @property
    def inventory_skew_enabled(self) -> bool:
        return self._inventory_skew_enabled

    @inventory_skew_enabled.setter
    def inventory_skew_enabled(self, value: bool):
        self._inventory_skew_enabled = value

    @property
    def inventory_target_base_pct(self) -> Decimal:
        return self._inventory_target_base_pct

    @inventory_target_base_pct.setter
    def inventory_target_base_pct(self, value: Decimal):
        self._inventory_target_base_pct = value

    @property
    def inventory_range_multiplier(self) -> Decimal:
        return self._inventory_range_multiplier

    @inventory_range_multiplier.setter
    def inventory_range_multiplier(self, value: Decimal):
        self._inventory_range_multiplier = value

    @property
    def hanging_orders_enabled(self) -> bool:
        return self._hanging_orders_enabled

    @hanging_orders_enabled.setter
    def hanging_orders_enabled(self, value: bool):
        self._hanging_orders_enabled = value

    @property
    def hanging_orders_cancel_pct(self) -> Decimal:
        return self._hanging_orders_cancel_pct

    @hanging_orders_cancel_pct.setter
    def hanging_orders_cancel_pct(self, value: Decimal):
        self._hanging_orders_cancel_pct = value

    @property
    def bid_spread(self) -> Decimal:
        return self._bid_spread

    @property
    def ask_spread(self) -> Decimal:
        return self._ask_spread

    @property
    def minimum_spread(self) -> Decimal:
        return self._minimum_spread

    @minimum_spread.setter
    def minimum_spread(self, value: Decimal):
        self._minimum_spread = value

    @property
    def maximum_spread(self) -> Decimal:
        return self._maximum_spread

    @maximum_spread.setter
    def maximum_spread(self, value: Decimal):
        self._maximum_spread = value

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
    def filled_order_delay(self) -> float:
        return self._filled_order_delay

    @filled_order_delay.setter
    def filled_order_delay(self, value: float):
        self._filled_order_delay = value

    @property
    def add_transaction_costs_to_orders(self) -> bool:
        return self._add_transaction_costs_to_orders

    @add_transaction_costs_to_orders.setter
    def add_transaction_costs_to_orders(self, value: bool):
        self._add_transaction_costs_to_orders = value

    @property
    def price_ceiling(self) -> Decimal:
        return self._price_ceiling

    @price_ceiling.setter
    def price_ceiling(self, value: Decimal):
        self._price_ceiling = value

    @property
    def price_floor(self) -> Decimal:
        return self._price_floor

    @price_floor.setter
    def price_floor(self, value: Decimal):
        self._price_floor = value

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
    def order_override(self):
        return self._order_override

    @order_override.setter
    def order_override(self, value: Dict[str, List[str]]):
        self._order_override = value

    def get_price(self) -> float:
        price_provider = self._market_info
        if self._price_type is PriceType.LastOwnTrade:
            price = self._last_own_trade_price
        elif self._price_type is PriceType.InventoryCost:
            price = price_provider.get_price_by_type(PriceType.MidPrice)
        else:
            price = price_provider.get_price_by_type(self._price_type)

        if price.is_nan():
            price = price_provider.get_price_by_type(PriceType.MidPrice)

        return price

    @property
    def aroon_up(self) -> float:
        return self._aroon_osc.c_aroon_up()

    @property
    def aroon_down(self) -> float:
        return self._aroon_osc.c_aroon_down()

    @property
    def aroon_osc(self) -> float:
        return self._aroon_osc.c_aroon_osc()

    @property
    def aroon_full(self) -> bool:
        return bool(self._aroon_osc.c_full())

    @property
    def aroon_period_count(self) -> int:
        return self._aroon_osc.c_aroon_period_count()

    @property
    def aroon_periods(self) -> List[OscillatorPeriod]:
        return self._aroon_osc.c_aroon_periods()

    @property
    def aroon_last_period(self) -> OscillatorPeriod:
        return self._aroon_osc.c_last_period()

    @property
    def min_max_spread_diff(self) -> Decimal:
        return self._min_max_spread_diff

    @property
    def trend_factor(self) -> Decimal:
        return self._trend_factor

    @property
    def ask_increase(self) -> Decimal:
        return self._ask_increase

    @property
    def bid_increase(self) -> Decimal:
        return self._bid_increase

    def get_last_price(self) -> Decimal:
        last_price = self._market_info.get_price_by_type(PriceType.LastTrade)
        if not last_price:
            return self.get_mid_price()
        return last_price

    def get_mid_price(self) -> float:
        return self.c_get_mid_price()

    cdef object c_get_mid_price(self):
        return self._market_info.get_mid_price()

    @property
    def hanging_order_ids(self) -> List[str]:
        return self._hanging_order_ids

    @property
    def market_info_to_active_orders(self) -> Dict[MarketTradingPairTuple, List[LimitOrder]]:
        return self._sb_order_tracker.market_pair_to_active_orders

    @property
    def active_orders(self) -> List[LimitOrder]:
        if self._market_info not in self.market_info_to_active_orders:
            return []
        return self.market_info_to_active_orders[self._market_info]

    @property
    def active_buys(self) -> List[LimitOrder]:
        return [o for o in self.active_orders if o.is_buy]

    @property
    def active_sells(self) -> List[LimitOrder]:
        return [o for o in self.active_orders if not o.is_buy]

    @property
    def active_non_hanging_orders(self) -> List[LimitOrder]:
        orders = [o for o in self.active_orders if o.client_order_id not in self._hanging_order_ids]
        return orders

    @property
    def logging_options(self) -> int:
        return self._logging_options

    @logging_options.setter
    def logging_options(self, int64_t logging_options):
        self._logging_options = logging_options

    @property
    def order_tracker(self):
        return self._sb_order_tracker

    def inventory_skew_stats_data_frame(self) -> Optional[pd.DataFrame]:
        cdef:
            ExchangeBase market = self._market_info.market

        price = self.get_price()
        base_asset_amount, quote_asset_amount = self.c_get_adjusted_available_balance(self.active_orders)
        total_order_size = calculate_total_order_size(self._order_amount, self._order_level_amount, self._order_levels)

        base_asset_value = base_asset_amount * price
        quote_asset_value = quote_asset_amount / price if price > s_decimal_zero else s_decimal_zero
        total_value = base_asset_amount + quote_asset_value
        total_value_in_quote = (base_asset_amount * price) + quote_asset_amount

        base_asset_ratio = (base_asset_amount / total_value
                            if total_value > s_decimal_zero
                            else s_decimal_zero)
        quote_asset_ratio = Decimal("1") - base_asset_ratio if total_value > 0 else 0
        target_base_ratio = self._inventory_target_base_pct
        inventory_range_multiplier = self._inventory_range_multiplier
        target_base_amount = (total_value * target_base_ratio
                              if price > s_decimal_zero
                              else s_decimal_zero)
        target_base_amount_in_quote = target_base_ratio * total_value_in_quote
        target_quote_amount = (1 - target_base_ratio) * total_value_in_quote

        base_asset_range = total_order_size * self._inventory_range_multiplier
        base_asset_range = min(base_asset_range, total_value * Decimal("0.5"))
        high_water_mark = target_base_amount + base_asset_range
        low_water_mark = max(target_base_amount - base_asset_range, s_decimal_zero)
        low_water_mark_ratio = (low_water_mark / total_value
                                if total_value > s_decimal_zero
                                else s_decimal_zero)
        high_water_mark_ratio = (high_water_mark / total_value
                                 if total_value > s_decimal_zero
                                 else s_decimal_zero)
        high_water_mark_ratio = min(1.0, high_water_mark_ratio)
        total_order_size_ratio = (self._order_amount * Decimal("2") / total_value
                                  if total_value > s_decimal_zero
                                  else s_decimal_zero)
        bid_ask_ratios = c_calculate_bid_ask_ratios_from_base_asset_ratio(
            float(base_asset_amount),
            float(quote_asset_amount),
            float(price),
            float(target_base_ratio),
            float(base_asset_range)
        )
        inventory_skew_df = pd.DataFrame(data=[
            [f"Target Value ({self.quote_asset})", f"{target_base_amount_in_quote:.4f}",
             f"{target_quote_amount:.4f}"],
            ["Current %", f"{base_asset_ratio:.1%}", f"{quote_asset_ratio:.1%}"],
            ["Target %", f"{target_base_ratio:.1%}", f"{1 - target_base_ratio:.1%}"],
            ["Inventory Range", f"{low_water_mark_ratio:.1%} - {high_water_mark_ratio:.1%}",
             f"{1 - high_water_mark_ratio:.1%} - {1 - low_water_mark_ratio:.1%}"],
            ["Order Adjust %", f"{bid_ask_ratios.bid_ratio:.1%}", f"{bid_ask_ratios.ask_ratio:.1%}"]
        ])
        return inventory_skew_df

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

    def active_orders_df(self) -> pd.DataFrame:
        price = self.get_price()
        active_orders = self.active_orders
        no_sells = len([o for o in active_orders if not o.is_buy and o.client_order_id not in self._hanging_order_ids])
        active_orders.sort(key=lambda x: x.price, reverse=True)
        columns = ["Level", "Type", "Price", "Spread", "Amount (Orig)", "Amount (Adj)", "Age"]
        data = []
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
            spread = 0 if price == 0 else abs(order.price - price)/price
            age = "n/a"
            # // indicates order is a paper order so 'n/a'. For real orders, calculate age.
            if "//" not in order.client_order_id:
                age = pd.Timestamp(int(time.time()) - int(order.client_order_id[-16:])/1e6,
                                   unit='s').strftime('%H:%M:%S')
            amount_orig = "" if level is None else self._order_amount + ((level - 1) * self._order_level_amount)
            data.append([
                "hang" if order.client_order_id in self._hanging_order_ids else level,
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
        markets_columns = ["Exchange", "Market", "Best Bid", "Best Ask", f"Ref Price ({self._price_type.name})"]
        if self._price_type is PriceType.LastOwnTrade and self._last_own_trade_price.is_nan():
            markets_columns[-1] = "Ref Price (MidPrice)"
        market_books = [(self._market_info.market, self._market_info.trading_pair)]
        for market, trading_pair in market_books:
            bid_price = market.get_price(trading_pair, False)
            ask_price = market.get_price(trading_pair, True)
            ref_price = float("nan")
            markets_data.append([
                market.display_name,
                trading_pair,
                float(bid_price),
                float(ask_price),
                float(ref_price)
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

        assets_df = self.pure_mm_assets_df(not self._inventory_skew_enabled)
        # append inventory skew stats.
        if self._inventory_skew_enabled:
            inventory_skew_df = self.inventory_skew_stats_data_frame()
            assets_df = assets_df.append(inventory_skew_df)

        first_col_length = max(*assets_df[0].apply(len))
        df_lines = assets_df.to_string(index=False, header=False,
                                       formatters={0: ("{:<" + str(first_col_length) + "}").format}).split("\n")
        lines.extend(["", "  Assets:"] + ["    " + line for line in df_lines])

        # See if there're any open orders.
        if len(self.active_orders) > 0:
            df = self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        else:
            lines.extend(["", "  No active maker orders."])

        last_aroon_period = self.aroon_last_period
        lines.extend([
            "",
            f"  Aroon Indicators:",
            f"    Aroon Up = {self.aroon_up:.5g}",
            f"    Aroon Down = {self.aroon_down:.5g}",
            f"    Aroon Osc = {self.aroon_osc:.3g}",
            f"    Aroon Indicator Full = {self.aroon_full}, Total periods {self.aroon_period_count}",
            f"    Current Period (start: {last_aroon_period.start:.0f}, end: {last_aroon_period.end:.0f}, high: {last_aroon_period.high:.5g}, low: {last_aroon_period.low:.5g})",
            f"    Adjusted Ask Spread = {self.ask_spread:.2%}",
            f"    Adjusted Bid Spread = {self.bid_spread:.2%}",
        ])
        if self.aroon_full or (0 < self._minimum_periods <= self.aroon_period_count):
            lines.extend([
                f"    Calculation params = (spread_diff: {self.min_max_spread_diff:.4%}, ask_increase: {self.ask_increase:.4%}, bid_increase: {self.bid_increase:.4%}, trend_factor: {self.trend_factor:.4%}, osc_strength_factor: {self._aroon_osc_strength_factor:.2g})",
                f"    Ask Spread formula = ({self._minimum_spread:.5g} + ({self.min_max_spread_diff:.6g} * (1 - ({self.aroon_up} / 100)))) * ( 1 + ({self.aroon_osc} / 100 * {self._aroon_osc_strength_factor:.2g}))",
                f"    Bid Spread formula = ({self._minimum_spread:.5g} + ({self.min_max_spread_diff:.6g} * (1 - ({self.aroon_down} / 100)))) * ( 1 - ({self.aroon_osc} / 100 * {self._aroon_osc_strength_factor:.2g}))",
            ])

        warning_lines.extend(self.balance_warning([self._market_info]))

        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    # The following exposed Python functions are meant for unit tests
    # ---------------------------------------------------------------
    def execute_orders_proposal(self, proposal: Proposal):
        return self.c_execute_orders_proposal(proposal)

    def cancel_order(self, order_id: str):
        return self.c_cancel_order(self._market_info, order_id)

    # ---------------------------------------------------------------

    cdef c_start(self, Clock clock, double timestamp):
        StrategyBase.c_start(self, clock, timestamp)
        self._last_timestamp = timestamp
        # start tracking any restored limit order
        restored_order_ids = self.c_track_restored_orders(self.market_info)
        # make restored order hanging orders
        for order_id in restored_order_ids:
            self._hanging_order_ids.append(order_id)

    cdef c_tick(self, double timestamp):
        StrategyBase.c_tick(self, timestamp)
        cdef:
            int64_t current_tick = <int64_t>(timestamp // self._status_report_interval)
            int64_t last_tick = <int64_t>(self._last_timestamp // self._status_report_interval)
            bint should_report_warnings = ((current_tick > last_tick) and
                                           (self._logging_options & self.OPTION_LOG_STATUS_REPORT))
            cdef object proposal
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

            proposal = None
            asset_mid_price = Decimal("0")
            # update the Aroon Oscillator Indicator with the last trade price data
            self._aroon_osc.c_add_tick(self._current_timestamp, self.get_last_price())
            # use the Aroon Oscillator Indicator to calculate the desired spreads
            self.c_adjust_spreads()
            # asset_mid_price = self.c_set_mid_price(market_info)
            if self._create_timestamp <= self._current_timestamp:
                # 1. Create base order proposals
                proposal = self.c_create_base_proposal()
                # 2. Apply functions that limit numbers of buys and sells proposal
                self.c_apply_order_levels_modifiers(proposal)
                # 3. Apply functions that modify orders price
                self.c_apply_order_price_modifiers(proposal)
                # 4. Apply functions that modify orders size
                self.c_apply_order_size_modifiers(proposal)
                # 5. Apply budget constraint, i.e. can't buy/sell more than what you have.
                self.c_apply_budget_constraint(proposal)

                if not self._take_if_crossed:
                    self.c_filter_out_takers(proposal)
            self.c_cancel_active_orders(proposal)
            self.c_cancel_hanging_orders()
            self.c_cancel_orders_below_min_spread()
            if self._is_debug:
                self.dump_debug_variables()
            refresh_proposal = self.c_aged_order_refresh()
            # Firstly restore cancelled aged order
            if refresh_proposal is not None:
                self.c_execute_orders_proposal(refresh_proposal)
            if self.c_to_create_orders(proposal):
                self.c_execute_orders_proposal(proposal)
        finally:
            self._last_timestamp = timestamp

    cdef c_adjust_spreads(self):
        self._min_max_spread_diff = self._maximum_spread - self._minimum_spread

        if self._aroon_osc.c_full() or (0 < self._minimum_periods <= self._aroon_osc.c_aroon_period_count()):
            # make aroon_up a percent and invert it for the ask spread, when aroon up is high, we want to sell
            self._ask_increase = (self._min_max_spread_diff * (s_decimal_one_oh - Decimal(self._aroon_osc.c_aroon_up()) / s_decimal_one_hundo))
            # make aroon_down a percent and invert it for the bid spread, when aroon down is high, we want to buy
            self._bid_increase = (self._min_max_spread_diff * (s_decimal_one_oh - Decimal(self._aroon_osc.c_aroon_down()) / s_decimal_one_hundo))
            # trend factor is another percentage to adjust the spread by. If there is an ongoing strong trend, we don't want to execute our orders too early
            self._trend_factor = Decimal(self._aroon_osc.c_aroon_osc()) / s_decimal_one_hundo * self._aroon_osc_strength_factor
            # aroon_osc 100% strong uptrend, likely to continue. Adjust the spread_increase to inhibit trading
            self._ask_spread = (self._minimum_spread + self._ask_increase) * (s_decimal_one_oh + self._trend_factor)
            # aroon_osc -100% strong downtrend and likely to continue. Adjust the spread_increase to inhibit trading
            self._bid_spread = (self._minimum_spread + self._bid_increase) * (s_decimal_one_oh - self._trend_factor)

            # adjust spreads to not exceed min/max spreads
            self._ask_spread = min(max(self._ask_spread, self._minimum_spread), self._maximum_spread)
            self._bid_spread = min(max(self._bid_spread, self._minimum_spread), self._maximum_spread)
        else:
            # when aroon isn't ready, just set the spreads to middle of min/max
            self._bid_spread = self._ask_spread = self._minimum_spread + (self._min_max_spread_diff * Decimal("0.5"))

        return None

    cdef object c_create_base_proposal(self):
        cdef:
            ExchangeBase market = self._market_info.market
            list buys = []
            list sells = []

        buy_reference_price = sell_reference_price = self.get_price()

        # First to check if a customized order override is configured, otherwise the proposal will be created according
        # to order spread, amount, and levels setting.
        order_override = self._order_override
        if order_override is not None and len(order_override) > 0:
            for key, value in order_override.items():
                if str(value[0]) in ["buy", "sell"]:
                    if str(value[0]) == "buy":
                        price = buy_reference_price * (Decimal("1") - Decimal(str(value[1])) / Decimal("100"))
                        price = market.c_quantize_order_price(self.trading_pair, price)
                        size = Decimal(str(value[2]))
                        size = market.c_quantize_order_amount(self.trading_pair, size)
                        if size > 0 and price > 0:
                            buys.append(PriceSize(price, size))
                    elif str(value[0]) == "sell":
                        price = sell_reference_price * (Decimal("1") + Decimal(str(value[1])) / Decimal("100"))
                        price = market.c_quantize_order_price(self.trading_pair, price)
                        size = Decimal(str(value[2]))
                        size = market.c_quantize_order_amount(self.trading_pair, size)
                        if size > 0 and price > 0:
                            sells.append(PriceSize(price, size))
        else:
            for level in range(0, self._buy_levels):
                price = buy_reference_price * (Decimal("1") - self._bid_spread - (level * self._order_level_spread))
                price = market.c_quantize_order_price(self.trading_pair, price)
                size = self._order_amount + (self._order_level_amount * level)
                size = market.c_quantize_order_amount(self.trading_pair, size)
                if size > 0:
                    buys.append(PriceSize(price, size))
            for level in range(0, self._sell_levels):
                price = sell_reference_price * (Decimal("1") + self._ask_spread + (level * self._order_level_spread))
                price = market.c_quantize_order_price(self.trading_pair, price)
                size = self._order_amount + (self._order_level_amount * level)
                size = market.c_quantize_order_amount(self.trading_pair, size)
                if size > 0:
                    sells.append(PriceSize(price, size))

        return Proposal(buys, sells)

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

    cdef c_apply_order_levels_modifiers(self, proposal):
        self.c_apply_price_band(proposal)

    cdef c_apply_price_band(self, proposal):
        if self._price_ceiling > 0 and self.get_price() >= self._price_ceiling:
            proposal.buys = []
        if self._price_floor > 0 and self.get_price() <= self._price_floor:
            proposal.sells = []

    cdef c_apply_order_price_modifiers(self, object proposal):
        if self._order_optimization_enabled:
            self.c_apply_order_optimization(proposal)

        if self._add_transaction_costs_to_orders:
            self.c_apply_add_transaction_costs(proposal)

    cdef c_apply_order_size_modifiers(self, object proposal):
        if self._inventory_skew_enabled:
            self.c_apply_inventory_skew(proposal)

    cdef c_apply_inventory_skew(self, object proposal):
        cdef:
            ExchangeBase market = self._market_info.market
            object bid_adj_ratio
            object ask_adj_ratio
            object size

        base_balance, quote_balance = self.c_get_adjusted_available_balance(self.active_orders)

        total_order_size = calculate_total_order_size(self._order_amount, self._order_level_amount, self._order_levels)
        bid_ask_ratios = c_calculate_bid_ask_ratios_from_base_asset_ratio(
            float(base_balance),
            float(quote_balance),
            float(self.get_price()),
            float(self._inventory_target_base_pct),
            float(total_order_size * self._inventory_range_multiplier)
        )
        bid_adj_ratio = Decimal(bid_ask_ratios.bid_ratio)
        ask_adj_ratio = Decimal(bid_ask_ratios.ask_ratio)

        for buy in proposal.buys:
            size = buy.size * bid_adj_ratio
            size = market.c_quantize_order_amount(self.trading_pair, size)
            buy.size = size

        for sell in proposal.sells:
            size = sell.size * ask_adj_ratio
            size = market.c_quantize_order_amount(self.trading_pair, size, sell.price)
            sell.size = size

    cdef c_apply_budget_constraint(self, object proposal):
        cdef:
            ExchangeBase market = self._market_info.market
            object quote_size
            object base_size
            object adjusted_amount

        base_balance, quote_balance = self.c_get_adjusted_available_balance(self.active_non_hanging_orders)

        for buy in proposal.buys:
            buy_fee = market.c_get_fee(self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.BUY,
                                       buy.size, buy.price)
            quote_size = buy.size * buy.price * (Decimal(1) + buy_fee.percent)

            # Adjust buy order size to use remaining balance if less than the order amount
            if quote_balance < quote_size:
                adjusted_amount = quote_balance / (buy.price * (Decimal("1") + buy_fee.percent))
                adjusted_amount = market.c_quantize_order_amount(self.trading_pair, adjusted_amount)
                # self.logger().info(f"Not enough balance for buy order (Size: {buy.size.normalize()}, Price: {buy.price.normalize()}), "
                #                    f"order_amount is adjusted to {adjusted_amount}")
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
                # self.logger().info(f"Not enough balance for sell order (Size: {sell.size.normalize()}, Price: {sell.price.normalize()}), "
                #                    f"order_amount is adjusted to {adjusted_amount}")
                sell.size = adjusted_amount
                base_balance = s_decimal_zero
            elif base_balance == s_decimal_zero:
                sell.size = s_decimal_zero
            else:
                base_balance -= base_size

        proposal.sells = [o for o in proposal.sells if o.size > 0]

    cdef c_filter_out_takers(self, object proposal):
        cdef:
            ExchangeBase market = self._market_info.market
            list new_buys = []
            list new_sells = []
        top_ask = market.c_get_price(self.trading_pair, True)
        if not top_ask.is_nan():
            proposal.buys = [buy for buy in proposal.buys if buy.price < top_ask]
        top_bid = market.c_get_price(self.trading_pair, False)
        if not top_bid.is_nan():
            proposal.sells = [sell for sell in proposal.sells if sell.price > top_bid]

    # Compare the market price with the top bid and top ask price
    cdef c_apply_order_optimization(self, object proposal):
        cdef:
            ExchangeBase market = self._market_info.market
            object own_buy_size = s_decimal_zero
            object own_sell_size = s_decimal_zero

        for order in self.active_orders:
            if order.is_buy:
                own_buy_size = order.quantity
            else:
                own_sell_size = order.quantity

        if len(proposal.buys) > 0:
            # Get the top bid price in the market using order_optimization_depth and your buy order volume
            top_bid_price = self._market_info.get_price_for_volume(
                False, self._bid_order_optimization_depth + own_buy_size).result_price
            price_quantum = market.c_get_order_price_quantum(
                self.trading_pair,
                top_bid_price
            )
            # Get the price above the top bid
            price_above_bid = (ceil(top_bid_price / price_quantum) + 1) * price_quantum

            # If the price_above_bid is lower than the price suggested by the top pricing proposal,
            # lower the price and from there apply the order_level_spread to each order in the next levels
            proposal.buys = sorted(proposal.buys, key = lambda p: p.price, reverse = True)
            lower_buy_price = min(proposal.buys[0].price, price_above_bid)
            for i, proposed in enumerate(proposal.buys):
                proposal.buys[i].price = market.c_quantize_order_price(self.trading_pair, lower_buy_price) * (1 - self.order_level_spread * i)

        if len(proposal.sells) > 0:
            # Get the top ask price in the market using order_optimization_depth and your sell order volume
            top_ask_price = self._market_info.get_price_for_volume(
                True, self._ask_order_optimization_depth + own_sell_size).result_price
            price_quantum = market.c_get_order_price_quantum(
                self.trading_pair,
                top_ask_price
            )
            # Get the price below the top ask
            price_below_ask = (floor(top_ask_price / price_quantum) - 1) * price_quantum

            # If the price_below_ask is higher than the price suggested by the pricing proposal,
            # increase your price and from there apply the order_level_spread to each order in the next levels
            proposal.sells = sorted(proposal.sells, key = lambda p: p.price)
            higher_sell_price = max(proposal.sells[0].price, price_below_ask)
            for i, proposed in enumerate(proposal.sells):
                proposal.sells[i].price = market.c_quantize_order_price(self.trading_pair, higher_sell_price) * (1 + self.order_level_spread * i)

    cdef object c_apply_add_transaction_costs(self, object proposal):
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
            limit_order_record = self._sb_order_tracker.c_get_limit_order(self._market_info, order_id)
        if limit_order_record is None:
            return
        active_sell_ids = [x.client_order_id for x in self.active_orders if not x.is_buy]

        if self._hanging_orders_enabled:
            # If the filled order is a hanging order, do nothing
            if order_id in self._hanging_order_ids:
                self.log_with_clock(
                    logging.INFO,
                    f"({self.trading_pair}) Hanging maker buy order {order_id} "
                    f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                    f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
                )
                self.notify_hb_app(
                    f"Hanging maker BUY order {limit_order_record.quantity} {limit_order_record.base_currency} @ "
                    f"{limit_order_record.price} {limit_order_record.quote_currency} is filled."
                )
                return

        # delay order creation by filled_order_dalay (in seconds)
        self._create_timestamp = self._current_timestamp + self._filled_order_delay
        self._cancel_timestamp = min(self._cancel_timestamp, self._create_timestamp)

        if self._hanging_orders_enabled:
            for other_order_id in active_sell_ids:
                self._hanging_order_ids.append(other_order_id)

        self._filled_buys_balance += 1
        self._last_own_trade_price = limit_order_record.price

        self.log_with_clock(
            logging.INFO,
            f"({self.trading_pair}) Maker buy order {order_id} "
            f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
            f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
        )
        self.notify_hb_app(
            f"Maker BUY order {limit_order_record.quantity} {limit_order_record.base_currency} @ "
            f"{limit_order_record.price} {limit_order_record.quote_currency} is filled."
        )

    cdef c_did_complete_sell_order(self, object order_completed_event):
        cdef:
            str order_id = order_completed_event.order_id
            LimitOrder limit_order_record = self._sb_order_tracker.c_get_limit_order(self._market_info, order_id)
        if limit_order_record is None:
            return
        active_buy_ids = [x.client_order_id for x in self.active_orders if x.is_buy]
        if self._hanging_orders_enabled:
            # If the filled order is a hanging order, do nothing
            if order_id in self._hanging_order_ids:
                self.log_with_clock(
                    logging.INFO,
                    f"({self.trading_pair}) Hanging maker sell order {order_id} "
                    f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                    f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
                )
                self.notify_hb_app(
                    f"Hanging maker SELL order {limit_order_record.quantity} {limit_order_record.base_currency} @ "
                    f"{limit_order_record.price} {limit_order_record.quote_currency} is filled."
                )
                return

        # delay order creation by filled_order_dalay (in seconds)
        self._create_timestamp = self._current_timestamp + self._filled_order_delay
        self._cancel_timestamp = min(self._cancel_timestamp, self._create_timestamp)

        if self._hanging_orders_enabled:
            for other_order_id in active_buy_ids:
                self._hanging_order_ids.append(other_order_id)

        self._filled_sells_balance += 1
        self._last_own_trade_price = limit_order_record.price

        self.log_with_clock(
            logging.INFO,
            f"({self.trading_pair}) Maker sell order {order_id} "
            f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
            f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
        )
        self.notify_hb_app(
            f"Maker SELL order {limit_order_record.quantity} {limit_order_record.base_currency} @ "
            f"{limit_order_record.price} {limit_order_record.quote_currency} is filled."
        )

    cdef bint c_is_within_tolerance(self, list current_prices, list proposal_prices):
        if len(current_prices) != len(proposal_prices):
            return False
        current_prices = sorted(current_prices)
        proposal_prices = sorted(proposal_prices)
        for current, proposal in zip(current_prices, proposal_prices):
            # if spread diff is more than the tolerance or order quantities are different, return false.
            if abs(proposal - current)/current > self._order_refresh_tolerance_pct:
                return False
        return True

    # Cancel active non hanging orders
    # Return value: whether order cancellation is deferred.
    cdef c_cancel_active_orders(self, object proposal):
        if self._cancel_timestamp > self._current_timestamp:
            return

        cdef:
            list active_orders = self.active_non_hanging_orders
            list active_buy_prices = []
            list active_sells = []
            bint to_defer_canceling = False
        if len(active_orders) == 0:
            return
        if proposal is not None and self._order_refresh_tolerance_pct >= 0:

            active_buy_prices = [Decimal(str(o.price)) for o in active_orders if o.is_buy]
            active_sell_prices = [Decimal(str(o.price)) for o in active_orders if not o.is_buy]
            proposal_buys = [buy.price for buy in proposal.buys]
            proposal_sells = [sell.price for sell in proposal.sells]
            if self.c_is_within_tolerance(active_buy_prices, proposal_buys) and \
                    self.c_is_within_tolerance(active_sell_prices, proposal_sells):
                to_defer_canceling = True

        if not to_defer_canceling:
            for order in active_orders:
                self.c_cancel_order(self._market_info, order.client_order_id)
        else:
            # self.logger().info(f"Not cancelling active orders since difference between new order prices "
            #                    f"and current order prices is within "
            #                    f"{self._order_refresh_tolerance_pct:.2%} order_refresh_tolerance_pct")
            self.set_timers()

    cdef c_cancel_hanging_orders(self):
        cdef:
            object price = self.get_price()
            list active_orders = self.active_orders
            list orders
            LimitOrder order
        for h_order_id in self._hanging_order_ids:
            orders = [o for o in active_orders if o.client_order_id == h_order_id]
            if orders and price > 0:
                order = orders[0]
                if abs(order.price - price)/price >= self._hanging_orders_cancel_pct:
                    self.c_cancel_order(self._market_info, order.client_order_id)

    # Cancel Non-Hanging, Active Orders if Spreads are below minimum_spread
    cdef c_cancel_orders_below_min_spread(self):
        cdef:
            list active_orders = self.market_info_to_active_orders.get(self._market_info, [])
            object price = self.get_price()
        active_orders = [order for order in active_orders
                         if order.client_order_id not in self._hanging_order_ids]
        for order in active_orders:
            negation = -1 if order.is_buy else 1
            if (negation * (order.price - price) / price) < self._cancel_order_spread_threshold:
                self.logger().info(f"Order is below minimum spread ({self._cancel_order_spread_threshold})."
                                   f" Cancelling Order: ({'Buy' if order.is_buy else 'Sell'}) "
                                   f"ID - {order.client_order_id}")
                self.c_cancel_order(self._market_info, order.client_order_id)

    # Refresh all active order that are older that the _max_order_age
    cdef c_aged_order_refresh(self):
        cdef:
            list active_orders = self.active_orders
            list buys = []
            list sells = []

        for order in active_orders:
            age = 0 if "//" in order.client_order_id else \
                int(int(time.time()) - int(order.client_order_id[-16:])/1e6)

            # To prevent duplicating orders due to delay in receiving cancel response
            refresh_check = [o for o in active_orders if o.price == order.price
                             and o.quantity == order.quantity]
            if len(refresh_check) > 1:
                continue

            if age >= self._max_order_age:
                if order.is_buy:
                    buys.append(PriceSize(order.price, order.quantity))
                else:
                    sells.append(PriceSize(order.price, order.quantity))
                if order.client_order_id in self._hanging_order_ids:
                    self._hanging_aged_order_prices.append(order.price)
                self.logger().info(f"Refreshing {'Buy' if order.is_buy else 'Sell'} order with ID - "
                                   f"{order.client_order_id} because it reached maximum order age of "
                                   f"{self._max_order_age} seconds.")
                self.c_cancel_order(self._market_info, order.client_order_id)
        return Proposal(buys, sells)

    cdef bint c_to_create_orders(self, object proposal):
        return self._create_timestamp < self._current_timestamp and \
            proposal is not None and \
            len(self.active_non_hanging_orders) == 0

    cdef c_execute_orders_proposal(self, object proposal):
        cdef:
            double expiration_seconds = (self._order_refresh_time
                                         if ((self._market_info.market.name in self.RADAR_RELAY_TYPE_EXCHANGES) or
                                             (self._market_info.market.name == "bamboo_relay" and
                                              not self._market_info.market.use_coordinator))
                                         else NaN)
            str bid_order_id, ask_order_id
            bint orders_created = False

        if len(proposal.buys) > 0:
            if self._logging_options & self.OPTION_LOG_CREATE_ORDER:
                price_quote_str = [f"{buy.size.normalize()} {self.base_asset}, "
                                   f"{buy.price.normalize()} {self.quote_asset}"
                                   for buy in proposal.buys]
                self.logger().info(
                    f"({self.trading_pair}) Creating {len(proposal.buys)} bid orders "
                    f"at (Size, Price): {price_quote_str}"
                )
            for buy in proposal.buys:
                bid_order_id = self.c_buy_with_specific_market(
                    self._market_info,
                    buy.size,
                    order_type=self._limit_order_type,
                    price=buy.price,
                    expiration_seconds=expiration_seconds
                )
                if buy.price in self._hanging_aged_order_prices:
                    self._hanging_order_ids.append(bid_order_id)
                    self._hanging_aged_order_prices.remove(buy.price)
                orders_created = True
        if len(proposal.sells) > 0:
            if self._logging_options & self.OPTION_LOG_CREATE_ORDER:
                price_quote_str = [f"{sell.size.normalize()} {self.base_asset}, "
                                   f"{sell.price.normalize()} {self.quote_asset}"
                                   for sell in proposal.sells]
                self.logger().info(
                    f"({self.trading_pair}) Creating {len(proposal.sells)} ask "
                    f"orders at (Size, Price): {price_quote_str}"
                )
            for sell in proposal.sells:
                ask_order_id = self.c_sell_with_specific_market(
                    self._market_info,
                    sell.size,
                    order_type=self._limit_order_type,
                    price=sell.price,
                    expiration_seconds=expiration_seconds
                )
                if sell.price in self._hanging_aged_order_prices:
                    self._hanging_order_ids.append(ask_order_id)
                    self._hanging_aged_order_prices.remove(sell.price)
                orders_created = True
        if orders_created:
            self.set_timers()

    cdef set_timers(self):
        cdef double next_cycle = self._current_timestamp + self._order_refresh_time
        if self._create_timestamp <= self._current_timestamp:
            self._create_timestamp = next_cycle
        if self._cancel_timestamp <= self._current_timestamp:
            self._cancel_timestamp = min(self._create_timestamp, next_cycle)

    def notify_hb_app(self, msg: str):
        if self._hb_app_notification:
            from hummingbot.client.hummingbot_application import HummingbotApplication
            HummingbotApplication.main_application()._notify(msg)

    def get_price_type(self, price_type_str: str) -> PriceType:
        if price_type_str == "mid_price":
            return PriceType.MidPrice
        elif price_type_str == "best_bid":
            return PriceType.BestBid
        elif price_type_str == "best_ask":
            return PriceType.BestAsk
        elif price_type_str == "last_price":
            return PriceType.LastTrade
        elif price_type_str == 'last_own_trade_price':
            return PriceType.LastOwnTrade
        elif price_type_str == 'inventory_cost':
            return PriceType.InventoryCost
        else:
            raise ValueError(f"Unrecognized price type string {price_type_str}.")

    def dump_debug_variables(self):
        market = self._market_info.market
        mid_price = self.get_price()
        last_price = self.get_last_price()

        if not os.path.exists(self._debug_csv_path):
            df_header = pd.DataFrame([('mid_price',
                                       'last_price',
                                       'min_spread',
                                       'max_spread',
                                       'bid_spread',
                                       'ask_spread',
                                       'aroon_up',
                                       'aroon_down',
                                       'aroon_osc',
                                       'ask_increase',
                                       'bid_increase',
                                       'trend_factor')])
            df_header.to_csv(self._debug_csv_path, mode='a', header=False, index=False)
        df = pd.DataFrame([(mid_price,
                            last_price,
                            self._minimum_spread,
                            self._maximum_spread,
                            self._bid_spread,
                            self._ask_spread,
                            self.aroon_up,
                            self.aroon_down,
                            self.aroon_osc,
                            self.ask_increase,
                            self.bid_increase,
                            self.trend_factor)])
        df.to_csv(self._debug_csv_path, mode='a', header=False, index=False)
