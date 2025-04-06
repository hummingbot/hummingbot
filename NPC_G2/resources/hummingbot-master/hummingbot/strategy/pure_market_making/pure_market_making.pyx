import logging
from decimal import Decimal
from math import ceil, floor
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils import map_df_to_str
from hummingbot.strategy.asset_price_delegate cimport AssetPriceDelegate
from hummingbot.strategy.asset_price_delegate import AssetPriceDelegate
from hummingbot.strategy.hanging_orders_tracker import CreatedPairOfOrders, HangingOrdersTracker
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.order_book_asset_price_delegate cimport OrderBookAssetPriceDelegate
from hummingbot.strategy.strategy_base import StrategyBase
from hummingbot.strategy.utils import order_age
from .data_types import PriceSize, Proposal
from .inventory_cost_price_delegate import InventoryCostPriceDelegate
from .inventory_skew_calculator cimport c_calculate_bid_ask_ratios_from_base_asset_ratio
from .inventory_skew_calculator import calculate_total_order_size
from .pure_market_making_order_tracker import PureMarketMakingOrderTracker
from .moving_price_band import MovingPriceBand


NaN = float("nan")
s_decimal_zero = Decimal(0)
s_decimal_neg_one = Decimal(-1)
pmm_logger = None


cdef class PureMarketMakingStrategy(StrategyBase):
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
                    bid_spread: Decimal,
                    ask_spread: Decimal,
                    order_amount: Decimal,
                    order_levels: int = 1,
                    order_level_spread: Decimal = s_decimal_zero,
                    order_level_amount: Decimal = s_decimal_zero,
                    order_refresh_time: float = 30.0,
                    max_order_age: float = 1800.0,
                    order_refresh_tolerance_pct: Decimal = s_decimal_neg_one,
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
                    asset_price_delegate: AssetPriceDelegate = None,
                    inventory_cost_price_delegate: InventoryCostPriceDelegate = None,
                    price_type: str = "mid_price",
                    take_if_crossed: bool = False,
                    price_ceiling: Decimal = s_decimal_neg_one,
                    price_floor: Decimal = s_decimal_neg_one,
                    ping_pong_enabled: bool = False,
                    logging_options: int = OPTION_LOG_ALL,
                    status_report_interval: float = 900,
                    minimum_spread: Decimal = Decimal(0),
                    hb_app_notification: bool = False,
                    order_override: Dict[str, List[str]] = None,
                    split_order_levels_enabled: bool = False,
                    bid_order_level_spreads: List[Decimal] = None,
                    ask_order_level_spreads: List[Decimal] = None,
                    should_wait_order_cancel_confirmation: bool = True,
                    moving_price_band: Optional[MovingPriceBand] = None
                    ):
        if order_override is None:
            order_override = {}
        if moving_price_band is None:
            moving_price_band = MovingPriceBand()
        if price_ceiling != s_decimal_neg_one and price_ceiling < price_floor:
            raise ValueError("Parameter price_ceiling cannot be lower than price_floor.")
        self._sb_order_tracker = PureMarketMakingOrderTracker()
        self._market_info = market_info
        self._bid_spread = bid_spread
        self._ask_spread = ask_spread
        self._minimum_spread = minimum_spread
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
        self._hanging_orders_tracker = HangingOrdersTracker(self, hanging_orders_cancel_pct)
        self._order_optimization_enabled = order_optimization_enabled
        self._ask_order_optimization_depth = ask_order_optimization_depth
        self._bid_order_optimization_depth = bid_order_optimization_depth
        self._add_transaction_costs_to_orders = add_transaction_costs_to_orders
        self._asset_price_delegate = asset_price_delegate
        self._inventory_cost_price_delegate = inventory_cost_price_delegate
        self._price_type = self.get_price_type(price_type)
        self._take_if_crossed = take_if_crossed
        self._price_ceiling = price_ceiling
        self._price_floor = price_floor
        self._ping_pong_enabled = ping_pong_enabled
        self._ping_pong_warning_lines = []
        self._hb_app_notification = hb_app_notification
        self._order_override = order_override
        self._split_order_levels_enabled=split_order_levels_enabled
        self._bid_order_level_spreads=bid_order_level_spreads
        self._ask_order_level_spreads=ask_order_level_spreads
        self._cancel_timestamp = 0
        self._create_timestamp = 0
        self._limit_order_type = self._market_info.market.get_maker_order_type()
        if take_if_crossed:
            self._limit_order_type = OrderType.LIMIT
        self._all_markets_ready = False
        self._filled_buys_balance = 0
        self._filled_sells_balance = 0
        self._logging_options = logging_options
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self._last_own_trade_price = Decimal('nan')
        self._should_wait_order_cancel_confirmation = should_wait_order_cancel_confirmation
        self._moving_price_band = moving_price_band
        self.c_add_markets([market_info.market])

    def all_markets_ready(self):
        return all([market.ready for market in self._sb_markets])

    @property
    def market_info(self) -> MarketTradingPairTuple:
        return self._market_info

    @property
    def max_order_age(self) -> float:
        return self._max_order_age

    @property
    def minimum_spread(self) -> Decimal:
        return self._minimum_spread

    @property
    def ping_pong_enabled(self) -> bool:
        return self._ping_pong_enabled

    @property
    def ask_order_optimization_depth(self) -> Decimal:
        return self._ask_order_optimization_depth

    @property
    def bid_order_optimization_depth(self) -> Decimal:
        return self._bid_order_optimization_depth

    @property
    def price_type(self) -> PriceType:
        return self._price_type

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
        return self._hanging_orders_tracker._hanging_orders_cancel_pct

    @hanging_orders_cancel_pct.setter
    def hanging_orders_cancel_pct(self, value: Decimal):
        self._hanging_orders_tracker._hanging_orders_cancel_pct = value

    @property
    def bid_spread(self) -> Decimal:
        return self._bid_spread

    @bid_spread.setter
    def bid_spread(self, value: Decimal):
        self._bid_spread = value

    @property
    def ask_spread(self) -> Decimal:
        return self._ask_spread

    @ask_spread.setter
    def ask_spread(self, value: Decimal):
        self._ask_spread = value

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

    @property
    def split_order_levels_enabled(self):
        return self._split_order_levels_enabled

    @property
    def bid_order_level_spreads(self):
        return self._bid_order_level_spreads

    @property
    def ask_order_level_spreads(self):
        return self._ask_order_level_spreads

    @order_override.setter
    def order_override(self, value: Dict[str, List[str]]):
        self._order_override = value

    @property
    def moving_price_band_enabled(self) -> bool:
        return self._moving_price_band.enabled

    @moving_price_band_enabled.setter
    def moving_price_band_enabled(self, value: bool):
        self._moving_price_band.switch(value)

    @property
    def price_ceiling_pct(self) -> Decimal:
        return self._moving_price_band.price_ceiling_pct

    @price_ceiling_pct.setter
    def price_ceiling_pct(self, value: Decimal):
        self._moving_price_band.price_ceiling_pct = value
        self._moving_price_band.update(self._current_timestamp, self.get_price())

    @property
    def price_floor_pct(self) -> Decimal:
        return self._moving_price_band.price_floor_pct

    @price_floor_pct.setter
    def price_floor_pct(self, value: Decimal):
        self._moving_price_band.price_floor_pct = value
        self._moving_price_band.update(self._current_timestamp, self.get_price())

    @property
    def price_band_refresh_time(self) -> float:
        return self._moving_price_band.price_band_refresh_time

    @price_band_refresh_time.setter
    def price_band_refresh_time(self, value: Decimal):
        self._moving_price_band.price_band_refresh_time = value
        self._moving_price_band.update(self._current_timestamp, self.get_price())

    @property
    def moving_price_band(self) -> MovingPriceBand:
        return self._moving_price_band

    def get_price(self) -> Decimal:
        price_provider = self._asset_price_delegate or self._market_info
        if self._price_type is PriceType.LastOwnTrade:
            price = self._last_own_trade_price
        elif self._price_type is PriceType.InventoryCost:
            price = price_provider.get_price_by_type(PriceType.MidPrice)
        else:
            price = price_provider.get_price_by_type(self._price_type)

        if price.is_nan():
            price = price_provider.get_price_by_type(PriceType.MidPrice)

        return price

    def get_mid_price(self) -> Decimal:
        return self.c_get_mid_price()

    cdef object c_get_mid_price(self):
        cdef:
            AssetPriceDelegate delegate = self._asset_price_delegate
            object mid_price
        if self._asset_price_delegate is not None:
            mid_price = delegate.c_get_mid_price()
        else:
            mid_price = self._market_info.get_mid_price()
        return mid_price

    @property
    def hanging_order_ids(self) -> List[str]:
        return [o.order_id for o in self._hanging_orders_tracker.strategy_current_hanging_orders]

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
        orders = [o for o in self.active_orders if not self._hanging_orders_tracker.is_order_id_in_hanging_orders(o.client_order_id)]
        return orders

    @property
    def logging_options(self) -> int:
        return self._logging_options

    @logging_options.setter
    def logging_options(self, int64_t logging_options):
        self._logging_options = logging_options

    @property
    def hanging_orders_tracker(self):
        return self._hanging_orders_tracker

    @property
    def asset_price_delegate(self) -> AssetPriceDelegate:
        return self._asset_price_delegate

    @asset_price_delegate.setter
    def asset_price_delegate(self, value):
        self._asset_price_delegate = value

    @property
    def inventory_cost_price_delegate(self) -> AssetPriceDelegate:
        return self._inventory_cost_price_delegate

    @inventory_cost_price_delegate.setter
    def inventory_cost_price_delegate(self, value):
        self._inventory_cost_price_delegate = value

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
            amount_orig = ""
            if not is_hanging_order:
                if order.is_buy:
                    level = lvl_buy + 1
                    lvl_buy += 1
                else:
                    level = no_sells - lvl_sell
                    lvl_sell += 1
                amount_orig = self._order_amount + ((level - 1) * self._order_level_amount)
            else:
                level_for_calculation = lvl_buy if order.is_buy else lvl_sell
                amount_orig = self._order_amount + ((level_for_calculation - 1) * self._order_level_amount)
                level = "hang"
            spread = 0 if price == 0 else abs(order.price - price)/price
            age = pd.Timestamp(order_age(order, self._current_timestamp), unit='s').strftime('%H:%M:%S')
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
        markets_columns = ["Exchange", "Market", "Best Bid", "Best Ask", f"Ref Price ({self._price_type.name})"]
        if self._price_type is PriceType.LastOwnTrade and self._last_own_trade_price.is_nan():
            markets_columns[-1] = "Ref Price (MidPrice)"
        market_books = [(self._market_info.market, self._market_info.trading_pair)]
        if type(self._asset_price_delegate) is OrderBookAssetPriceDelegate:
            market_books.append((self._asset_price_delegate.market, self._asset_price_delegate.trading_pair))
        for market, trading_pair in market_books:
            bid_price = market.get_price(trading_pair, False)
            ask_price = market.get_price(trading_pair, True)
            ref_price = float("nan")
            if market == self._market_info.market and self._inventory_cost_price_delegate is not None:
                # We're using inventory_cost, show it's price
                ref_price = self._inventory_cost_price_delegate.get_price()
                if ref_price is None:
                    ref_price = self.get_price()
            elif market == self._market_info.market and self._asset_price_delegate is None:
                ref_price = self.get_price()
            elif (
                self._asset_price_delegate is not None
                and market == self._asset_price_delegate.market
                and self._price_type is not PriceType.LastOwnTrade
            ):
                ref_price = self._asset_price_delegate.get_price_by_type(self._price_type)
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
        warning_lines.extend(self._ping_pong_warning_lines)
        warning_lines.extend(self.network_warning([self._market_info]))

        markets_df = map_df_to_str(self.market_status_data_frame([self._market_info]))
        lines.extend(["", "  Markets:"] + ["    " + line for line in markets_df.to_string(index=False).split("\n")])

        assets_df = map_df_to_str(self.pure_mm_assets_df(not self._inventory_skew_enabled))
        # append inventory skew stats.
        if self._inventory_skew_enabled:
            inventory_skew_df = map_df_to_str(self.inventory_skew_stats_data_frame())
            assets_df = pd.concat(
                [assets_df, inventory_skew_df], join="inner")

        first_col_length = max(*assets_df[0].apply(len))
        df_lines = assets_df.to_string(index=False, header=False,
                                       formatters={0: ("{:<" + str(first_col_length) + "}").format}).split("\n")
        lines.extend(["", "  Assets:"] + ["    " + line for line in df_lines])

        # See if there're any open orders.
        if len(self.active_orders) > 0:
            df = map_df_to_str(self.active_orders_df())
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        else:
            lines.extend(["", "  No active maker orders."])

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

        self._hanging_orders_tracker.register_events(self.active_markets)

        if self._hanging_orders_enabled:
            # start tracking any restored limit order
            restored_order_ids = self.c_track_restored_orders(self.market_info)
            # make restored order hanging orders
            for order_id in restored_order_ids:
                order = next(o for o in self.market_info.market.limit_orders if o.client_order_id == order_id)
                if order:
                    self._hanging_orders_tracker.add_as_hanging_order(order)

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
            cdef object proposal
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

            proposal = None
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

            self._hanging_orders_tracker.process_tick()

            self.c_cancel_active_orders_on_max_age_limit()
            self.c_cancel_active_orders(proposal)
            self.c_cancel_orders_below_min_spread()
            if self.c_to_create_orders(proposal):
                self.c_execute_orders_proposal(proposal)
        finally:
            self._last_timestamp = timestamp

    cdef object c_create_base_proposal(self):
        cdef:
            ExchangeBase market = self._market_info.market
            list buys = []
            list sells = []

        buy_reference_price = sell_reference_price = self.get_price()

        if self._inventory_cost_price_delegate is not None:
            inventory_cost_price = self._inventory_cost_price_delegate.get_price()
            if inventory_cost_price is not None:
                # Only limit sell price. Buy are always allowed.
                sell_reference_price = max(inventory_cost_price, sell_reference_price)
            else:
                base_balance = float(market.get_balance(self._market_info.base_asset))
                if base_balance > 0:
                    raise RuntimeError("Initial inventory price is not set while inventory_cost feature is active.")

        # First to check if a customized order override is configured, otherwise the proposal will be created according
        # to order spread, amount, and levels setting.
        order_override = self._order_override
        if order_override is not None and len(order_override) > 0:
            for key, value in order_override.items():
                if str(value[0]) in ["buy", "sell"]:
                    if str(value[0]) == "buy" and not buy_reference_price.is_nan():
                        price = buy_reference_price * (Decimal("1") - Decimal(str(value[1])) / Decimal("100"))
                        price = market.c_quantize_order_price(self.trading_pair, price)
                        size = Decimal(str(value[2]))
                        size = market.c_quantize_order_amount(self.trading_pair, size)
                        if size > 0 and price > 0:
                            buys.append(PriceSize(price, size))
                    elif str(value[0]) == "sell" and not sell_reference_price.is_nan():
                        price = sell_reference_price * (Decimal("1") + Decimal(str(value[1])) / Decimal("100"))
                        price = market.c_quantize_order_price(self.trading_pair, price)
                        size = Decimal(str(value[2]))
                        size = market.c_quantize_order_amount(self.trading_pair, size)
                        if size > 0 and price > 0:
                            sells.append(PriceSize(price, size))
        else:
            if not buy_reference_price.is_nan():
                for level in range(0, self._buy_levels):
                    price = buy_reference_price * (Decimal("1") - self._bid_spread - (level * self._order_level_spread))
                    price = market.c_quantize_order_price(self.trading_pair, price)
                    size = self._order_amount + (self._order_level_amount * level)
                    size = market.c_quantize_order_amount(self.trading_pair, size)
                    if size > 0:
                        buys.append(PriceSize(price, size))
            if not sell_reference_price.is_nan():
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
        if self.moving_price_band_enabled:
            self.c_apply_moving_price_band(proposal)
        if self._ping_pong_enabled:
            self.c_apply_ping_pong(proposal)

    cdef c_apply_price_band(self, proposal):
        if self._price_ceiling > 0 and self.get_price() >= self._price_ceiling:
            proposal.buys = []
        if self._price_floor > 0 and self.get_price() <= self._price_floor:
            proposal.sells = []

    cdef c_apply_moving_price_band(self, proposal):
        price = self.get_price()
        self._moving_price_band.check_and_update_price_band(
            self.current_timestamp, price)
        if self._moving_price_band.check_price_ceiling_exceeded(price):
            proposal.buys = []
        if self._moving_price_band.check_price_floor_exceeded(price):
            proposal.sells = []

    cdef c_apply_ping_pong(self, object proposal):
        self._ping_pong_warning_lines = []
        if self._filled_buys_balance == self._filled_sells_balance:
            self._filled_buys_balance = self._filled_sells_balance = 0
        if self._filled_buys_balance > 0:
            proposal.buys = proposal.buys[self._filled_buys_balance:]
            self._ping_pong_warning_lines.extend(
                [f"  Ping-pong removed {self._filled_buys_balance} buy orders."]
            )
        if self._filled_sells_balance > 0:
            proposal.sells = proposal.sells[self._filled_sells_balance:]
            self._ping_pong_warning_lines.extend(
                [f"  Ping-pong removed {self._filled_sells_balance} sell orders."]
            )

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
                if self._split_order_levels_enabled:
                    proposal.buys[i].price = (market.c_quantize_order_price(self.trading_pair, lower_buy_price)
                                              * (1 - self._bid_order_level_spreads[i] / Decimal("100"))
                                              / (1-self._bid_order_level_spreads[0] / Decimal("100")))
                    continue
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
                if self._split_order_levels_enabled:
                    proposal.sells[i].price = (market.c_quantize_order_price(self.trading_pair, higher_sell_price)
                                               * (1 + self._ask_order_level_spreads[i] / Decimal("100"))
                                               / (1 + self._ask_order_level_spreads[0] / Decimal("100")))
                    continue
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

            if self._inventory_cost_price_delegate is not None:
                self._inventory_cost_price_delegate.process_order_fill_event(order_filled_event)

    cdef c_did_complete_buy_order(self, object order_completed_event):
        cdef:
            str order_id = order_completed_event.order_id
            limit_order_record = self._sb_order_tracker.c_get_limit_order(self._market_info, order_id)
        if limit_order_record is None:
            return
        active_sell_ids = [x.client_order_id for x in self.active_orders if not x.is_buy]

        if self._hanging_orders_enabled:
            # If the filled order is a hanging order, do nothing
            if order_id in self.hanging_order_ids:
                self.log_with_clock(
                    logging.INFO,
                    f"({self.trading_pair}) Hanging maker buy order {order_id} "
                    f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                    f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
                )
                self.notify_hb_app_with_timestamp(
                    f"Hanging maker BUY order {limit_order_record.quantity} {limit_order_record.base_currency} @ "
                    f"{limit_order_record.price} {limit_order_record.quote_currency} is filled."
                )
                return

        # delay order creation by filled_order_dalay (in seconds)
        self._create_timestamp = self._current_timestamp + self._filled_order_delay
        self._cancel_timestamp = min(self._cancel_timestamp, self._create_timestamp)

        self._filled_buys_balance += 1
        self._last_own_trade_price = limit_order_record.price

        self.log_with_clock(
            logging.INFO,
            f"({self.trading_pair}) Maker buy order {order_id} "
            f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
            f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
        )
        self.notify_hb_app_with_timestamp(
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
            if order_id in self.hanging_order_ids:
                self.log_with_clock(
                    logging.INFO,
                    f"({self.trading_pair}) Hanging maker sell order {order_id} "
                    f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                    f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
                )
                self.notify_hb_app_with_timestamp(
                    f"Hanging maker SELL order {limit_order_record.quantity} {limit_order_record.base_currency} @ "
                    f"{limit_order_record.price} {limit_order_record.quote_currency} is filled."
                )
                return

        # delay order creation by filled_order_dalay (in seconds)
        self._create_timestamp = self._current_timestamp + self._filled_order_delay
        self._cancel_timestamp = min(self._cancel_timestamp, self._create_timestamp)

        self._filled_sells_balance += 1
        self._last_own_trade_price = limit_order_record.price

        self.log_with_clock(
            logging.INFO,
            f"({self.trading_pair}) Maker sell order {order_id} "
            f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
            f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
        )
        self.notify_hb_app_with_timestamp(
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

    cdef c_cancel_active_orders_on_max_age_limit(self):
        """
        Cancels active non hanging orders if they are older than max age limit
        """
        cdef:
            list active_orders = self.active_non_hanging_orders

        if active_orders and any(order_age(o, self._current_timestamp) > self._max_order_age for o in active_orders):
            for order in active_orders:
                self.c_cancel_order(self._market_info, order.client_order_id)

    cdef c_cancel_active_orders(self, object proposal):
        """
        Cancels active non hanging orders, checks if the order prices are within tolerance threshold
        """
        if self._cancel_timestamp > self._current_timestamp:
            return

        cdef:
            list active_orders = self.active_non_hanging_orders
            list active_buy_prices = []
            list active_sells = []
            bint to_defer_canceling = False
        if len(active_orders) == 0:
            return
        if proposal is not None and \
                self._order_refresh_tolerance_pct >= 0:

            active_buy_prices = [Decimal(str(o.price)) for o in active_orders if o.is_buy]
            active_sell_prices = [Decimal(str(o.price)) for o in active_orders if not o.is_buy]
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
        # else:
        #     self.set_timers()

    # Cancel Non-Hanging, Active Orders if Spreads are below minimum_spread
    cdef c_cancel_orders_below_min_spread(self):
        cdef:
            list active_orders = self.market_info_to_active_orders.get(self._market_info, [])
            object price = self.get_price()
        active_orders = [order for order in active_orders
                         if order.client_order_id not in self.hanging_order_ids]
        for order in active_orders:
            negation = -1 if order.is_buy else 1
            if (negation * (order.price - price) / price) < self._minimum_spread:
                self.logger().info(f"Order is below minimum spread ({self._minimum_spread})."
                                   f" Canceling Order: ({'Buy' if order.is_buy else 'Sell'}) "
                                   f"ID - {order.client_order_id}")
                self.c_cancel_order(self._market_info, order.client_order_id)

    cdef bint c_to_create_orders(self, object proposal):
        non_hanging_orders_non_cancelled = [o for o in self.active_non_hanging_orders if not
                                            self._hanging_orders_tracker.is_potential_hanging_order(o)]
        return (self._create_timestamp < self._current_timestamp
                and (not self._should_wait_order_cancel_confirmation or
                     len(self._sb_order_tracker.in_flight_cancels) == 0)
                and proposal is not None
                and len(non_hanging_orders_non_cancelled) == 0)

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
            self.set_timers()

    cdef set_timers(self):
        cdef double next_cycle = self._current_timestamp + self._order_refresh_time
        if self._create_timestamp <= self._current_timestamp:
            self._create_timestamp = next_cycle
        if self._cancel_timestamp <= self._current_timestamp:
            self._cancel_timestamp = min(self._create_timestamp, next_cycle)

    def notify_hb_app(self, msg: str):
        if self._hb_app_notification:
            super().notify_hb_app(msg)

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
        elif price_type_str == "custom":
            return PriceType.Custom
        else:
            raise ValueError(f"Unrecognized price type string {price_type_str}.")
