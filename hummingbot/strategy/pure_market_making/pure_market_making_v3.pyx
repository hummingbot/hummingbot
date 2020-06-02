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
from hummingbot.core.clock cimport Clock
from hummingbot.core.event.events import TradeType
from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.market.market_base cimport MarketBase
from hummingbot.market.market_base import (
    MarketBase,
    OrderType,
)
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_base import StrategyBase
from hummingbot.client.config.global_config_map import paper_trade_disabled

from .data_types import (
    Proposal,
    PriceSize
)
from .pure_market_making_order_tracker import PureMarketMakingOrderTracker

from .asset_price_delegate cimport AssetPriceDelegate
from .asset_price_delegate import AssetPriceDelegate
from .inventory_skew_calculator cimport c_calculate_bid_ask_ratios_from_base_asset_ratio


NaN = float("nan")
s_decimal_zero = Decimal(0)
s_decimal_neg_one = Decimal(-1)
s_logger = None


cdef class PureMarketMakingStrategyV3(StrategyBase):
    OPTION_LOG_CREATE_ORDER = 1 << 3
    OPTION_LOG_MAKER_ORDER_FILLED = 1 << 4
    OPTION_LOG_STATUS_REPORT = 1 << 5
    OPTION_LOG_ALL = 0x7fffffffffffffff

    # These are exchanges where you're expected to expire orders instead of actively cancelling them.
    RADAR_RELAY_TYPE_EXCHANGES = {"radar_relay", "bamboo_relay"}

    @classmethod
    def logger(cls):
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 market_info: MarketTradingPairTuple,
                 bid_spread: Decimal,
                 ask_spread: Decimal,
                 order_amount: Decimal,
                 order_levels: int = 1,
                 order_level_spread: Decimal = s_decimal_zero,
                 order_level_amount: Decimal = s_decimal_zero,
                 order_refresh_time: float = 30.0,
                 order_refresh_tolerance_pct: Decimal = s_decimal_neg_one,
                 filled_order_delay: float = 60.0,
                 inventory_skew_enabled: bool = False,
                 inventory_target_base_pct: Decimal = s_decimal_zero,
                 inventory_range_multiplier: Decimal = s_decimal_zero,
                 hanging_orders_enabled: bool = False,
                 hanging_orders_cancel_pct: Decimal = Decimal("0.1"),
                 order_optimization_enabled: bool = False,
                 order_optimization_depth: Decimal = s_decimal_zero,
                 add_transaction_costs_to_orders: bool = False,
                 asset_price_delegate: AssetPriceDelegate = None,
                 price_ceiling: Decimal = s_decimal_neg_one,
                 price_floor: Decimal = s_decimal_neg_one,
                 ping_pong_enabled: bool = False,
                 logging_options: int = OPTION_LOG_ALL,
                 status_report_interval: float = 900,
                 expiration_seconds: float = NaN,
                 ):

        if price_ceiling != s_decimal_neg_one and price_ceiling < price_floor:
            raise ValueError("Parameter price_ceiling cannot be lower than price_floor.")

        super().__init__()
        self._sb_order_tracker = PureMarketMakingOrderTracker()
        self._market_info = market_info
        self._bid_spread = bid_spread
        self._ask_spread = ask_spread
        self._order_amount = order_amount
        self._order_levels = order_levels
        self._buy_levels = order_levels
        self._sell_levels = order_levels
        self._order_level_spread = order_level_spread
        self._order_level_amount = order_level_amount
        self._order_refresh_time = order_refresh_time
        self._order_refresh_tolerance_pct = order_refresh_tolerance_pct
        self._filled_order_delay = filled_order_delay
        self._inventory_skew_enabled = inventory_skew_enabled
        self._inventory_target_base_pct = inventory_target_base_pct
        self._inventory_range_multiplier = inventory_range_multiplier
        self._hanging_orders_enabled = hanging_orders_enabled
        self._hanging_orders_cancel_pct = hanging_orders_cancel_pct
        self._order_optimization_enabled = order_optimization_enabled
        self._order_optimization_depth = order_optimization_depth
        self._add_transaction_costs_to_orders = add_transaction_costs_to_orders
        self._asset_price_delegate = asset_price_delegate
        self._price_ceiling = price_ceiling
        self._price_floor = price_floor
        self._ping_pong_enabled = ping_pong_enabled

        self._cancel_timestamp = 0
        self._create_timestamp = 0
        self._limit_order_type = OrderType.LIMIT
        if market_info.market.name == "binance" and paper_trade_disabled():
            self._limit_order_type = OrderType.LIMIT_MAKER
        self._all_markets_ready = False
        self._expiration_seconds = expiration_seconds
        self._filled_buys_sells_balance = 0
        self._hanging_order_ids = []
        self._logging_options = logging_options
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval

        self.c_add_markets([market_info.market])

    @property
    def mid_price(self):
        mid_price = self._market_info.get_mid_price()
        if self._asset_price_delegate is not None:
            mid_price = self._asset_price_delegate.c_get_mid_price()
        return mid_price

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
    def asset_price_delegate(self) -> AssetPriceDelegate:
        return self._asset_price_delegate

    @asset_price_delegate.setter
    def asset_price_delegate(self, value):
        self._asset_price_delegate = value

    @property
    def order_tracker(self):
        return self._sb_order_tracker

    def inventory_skew_stats_data_frame(self) -> Optional[pd.DataFrame]:
        cdef:
            MarketBase market = self._market_info.market

        trading_pair = self._market_info.trading_pair
        mid_price = ((market.c_get_price(trading_pair, True) + market.c_get_price(trading_pair, False)) *
                     Decimal("0.5"))
        base_asset_amount = market.c_get_balance(self._market_info.base_asset)
        quote_asset_amount = market.c_get_balance(self._market_info.quote_asset)
        base_asset_value = base_asset_amount * mid_price
        quote_asset_value = quote_asset_amount / mid_price if mid_price > s_decimal_zero else s_decimal_zero
        total_value = base_asset_amount + quote_asset_value
        total_value_in_quote = (base_asset_amount * mid_price) + quote_asset_amount

        base_asset_ratio = (base_asset_amount / total_value
                            if total_value > s_decimal_zero
                            else s_decimal_zero)
        quote_asset_ratio = Decimal("1") - base_asset_ratio if total_value > 0 else 0
        target_base_ratio = self._inventory_target_base_pct
        inventory_range_multiplier = self._inventory_range_multiplier
        target_base_amount = (total_value * target_base_ratio
                              if mid_price > s_decimal_zero
                              else s_decimal_zero)
        target_base_amount_in_quote = target_base_ratio * total_value_in_quote
        target_quote_amount = (1 - target_base_ratio) * total_value_in_quote
        base_asset_range = (self._order_amount * Decimal("2") * self._inventory_range_multiplier)
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
            float(mid_price),
            float(target_base_ratio),
            float(base_asset_range)
        )
        inventory_skew_df = pd.DataFrame(data=[
            [f"Target Value ({self._market_info.quote_asset})", f"{target_base_amount_in_quote:.4f}",
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
        mid_price = self.mid_price
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

    def active_orders_df(self) -> pd.DataFrame:
        mid_price = self.mid_price()
        active_orders = self.active_orders
        no_sells = len([o for o in active_orders if not o.is_buy and o.client_order_id not in self._hanging_order_ids])
        active_orders.sort(key=lambda x: x.price, reverse=True)
        columns = ["Level", "Type", "Price", "Spread", "Amount (Orig)", "Amount (Adj)", "Age", "Hang"]
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
            spread = 0 if mid_price == 0 else abs(order.price - mid_price)/mid_price
            age = "n/a"
            # // indicates order is a paper order so 'n/a'. For real orders, calculate age.
            if "//" not in order.client_order_id:
                age = pd.Timestamp(int(time.time()) - int(order.client_order_id[-16:])/1e6,
                                   unit='s').strftime('%H:%M:%S')
            amount_orig = "" if level is None else self._order_amount + ((level - 1) * self._order_level_amount)
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
        warning_lines.extend(self.network_warning([self._market_info]))

        markets_df = self.market_status_data_frame()
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

        warning_lines.extend(self.balance_warning([self._market_info]))

        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    # The following exposed Python functions are meant for unit tests
    # ---------------------------------------------------------------
    def execute_orders_proposal(self, proposal: Proposal):
        return self.c_execute_orders_proposal(proposal)

    def cancel_order(self, market_info: MarketTradingPairTuple, order_id: str):
        return self.c_cancel_order(market_info, order_id)

    # ---------------------------------------------------------------

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
            asset_mid_price = Decimal("0")
            # asset_mid_price = self.c_set_mid_price(market_info)
            if self._create_timestamp <= self._current_timestamp:
                # 1. Set number of buy and sell order levels for order proposal
                self.c_set_buy_sell_levels()
                # 2. Create base order proposals
                proposal =self.c_create_base_proposal()
                # 3. Apply functions that modify orders price
                self.c_apply_order_price_modifiers(proposal)
                # 4. Apply functions that modify orders size
                self.c_apply_order_size_modifiers(proposal)

                self.c_filter_proposal_for_takers(proposal)
                print(f"Proposal: {proposal}")
            self.c_cancel_active_orders(proposal)
            self.c_cancel_hanging_orders()
            if self.c_to_create_orders(proposal):
                self.c_execute_orders_proposal(proposal)
        finally:
            self._last_timestamp = timestamp

    cdef c_set_buy_sell_levels(self):
        self.c_apply_ping_pong()
        self.c_apply_price_band()

    cdef c_apply_price_band(self):
        if self._price_ceiling > 0 and self.mid_price > self._price_ceiling:
            self._buy_levels = 0
        elif self._price_floor > 0 and self.mid_price < self._price_floor:
            self._sell_levels = 0
        else:
            self._buy_levels = self._order_levels
            self._sell_levels = self._order_levels

    cdef c_apply_ping_pong(self):
        if not self._ping_pong_enabled:
            return
        if self._filled_buys_sells_balance > 0:
            self._buy_levels = self._order_levels - self._filled_buys_sells_balance
        if self._filled_buys_sells_balance < 0:
            self._sell_levels = self._order_levels - abs(self._filled_buys_sells_balance)
        else:
            self._buy_levels = self._order_levels
            self._sell_levels = self._order_levels

    cdef object c_create_base_proposal(self):
        cdef:
            MarketBase market = self._market_info.market
            str trading_pair = self._market_info.trading_pair
            list buys = []
            list sells = []

        for level in range(0, self._buy_levels):
            price = self.mid_price * (Decimal("1") - self._bid_spread - (level * self._order_level_spread))
            price = market.c_quantize_order_price(trading_pair, price)
            size = self._order_amount + (self._order_level_amount * level)
            market.c_quantize_order_amount(trading_pair, size)
            buys.append(PriceSize(price, size))
        for level in range(0, self._sell_levels):
            price = self.mid_price * (Decimal("1") + self._ask_spread + (level * self._order_level_spread))
            price = market.c_quantize_order_price(trading_pair, price)
            size = self._order_amount + (self._order_level_amount * level)
            market.c_quantize_order_amount(trading_pair, size)
            sells.append(PriceSize(price, size))

        return Proposal(buys, sells)

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
            MarketBase market = self._market_info.market
            str base = self._market_info.trading_pair.split("-")[0]
            str quote = self._market_info.trading_pair.split("-")[1]
            object base_balance = market.c_get_available_balance(base)
            object quote_balance = market.c_get_available_balance(quote)

        for active_order in self.active_orders:
            if active_order.is_buy:
                quote_balance += active_order.quantity * active_order.price
            else:
                base_balance += active_order.quantity

        cdef:
            object bid_adj_ratio
            object ask_adj_ratio
            object size

        total_order_size = self._order_amount * Decimal("2")
        bid_ask_ratios = c_calculate_bid_ask_ratios_from_base_asset_ratio(
            float(base_balance),
            float(quote_balance),
            float(self.mid_price),
            float(self._inventory_target_base_pct),
            float(total_order_size * self._inventory_range_multiplier)
        )
        bid_adj_ratio = Decimal(bid_ask_ratios.bid_ratio)
        ask_adj_ratio = Decimal(bid_ask_ratios.ask_ratio)

        for buy in proposal.buys:
            size = buy.size * bid_adj_ratio
            size = market.c_quantize_order_amount(self._market_info.trading_pair, size)
            buy.size = size

        for sell in proposal.sells:
            size = sell.size * ask_adj_ratio
            size = market.c_quantize_order_amount(self._market_info.trading_pair, size, sell.price)
            sell.size = size

    cdef c_filter_proposal_for_takers(self, object proposal):
        cdef:
            MarketBase market = self._market_info.market
            list new_buys = []
            list new_sells = []
        top_ask = market.c_get_price(self._market_info.trading_pair, True)
        proposal.buys = [buy for buy in proposal.buys if buy.price < top_ask]
        top_bid = market.c_get_price(self._market_info.trading_pair, False)
        proposal.sells = [sell for sell in proposal.sells if sell.price > top_bid]

    # Compare the market price with the top bid and top ask price
    cdef c_apply_order_optimization(self, object proposal):
        cdef:
            MarketBase market = self._market_info.market
            object own_buy_order_depth = s_decimal_zero
            object own_sell_order_depth = s_decimal_zero

        # If there are multiple orders, do not jump prices
        if self._order_levels > 1:
            return

        for order in self.active_orders:
            if order.is_buy:
                own_buy_size = order.quantity
            else:
                own_sell_size = order.quantity

        # Get the top bid price in the market using order_optimization_depth and your buy order volume
        top_bid_price = self._market_info.get_price_for_volume(
            False, self._order_optimization_depth + own_buy_size).result_price
        price_quantum = market.c_get_order_price_quantum(
            self._market_info.trading_pair,
            top_bid_price
        )
        # Get the price above the top bid
        price_above_bid = (ceil(top_bid_price / price_quantum) + 1) * price_quantum

        # If the price_above_bid is lower than the price suggested by the pricing proposal,
        # lower your price to this
        lower_buy_price = min(proposal.buys[0].price, price_above_bid)
        proposal.buys[0].price = market.c_quantize_order_price(self._market_info.trading_pair, lower_buy_price)

        # Get the top ask price in the market using order_optimization_depth and your sell order volume
        top_ask_price = self._market_info.get_price_for_volume(
            True, self._order_optimization_depth + own_sell_size).result_price
        price_quantum = market.c_get_order_price_quantum(
            self._market_info.trading_pair,
            top_ask_price
        )
        # Get the price below the top ask
        price_below_ask = (floor(top_ask_price / price_quantum) - 1) * price_quantum

        # If the price_below_ask is higher than the price suggested by the pricing proposal,
        # increase your price to this
        higher_sell_price = max(proposal.sells[0].price, price_below_ask)
        proposal.sells[0].price = market.c_quantize_order_price(self._market_info.trading_pair, higher_sell_price)

    cdef object c_apply_add_transaction_costs(self, object proposal):
        cdef:
            MarketBase market = self._market_info.market
        for buy in proposal.buys:
            fee = market.c_get_fee(self._market_info.base_asset, self._market_info.quote_asset,
                                   OrderType.LIMIT, TradeType.BUY, buy.size, buy.price)
            price = buy.price * (Decimal(1) - fee.percent)
            buy.price = market.c_quantize_order_price(self._market_info.trading_pair, price)
        for sell in proposal.sells:
            fee = market.c_get_fee(self._market_info.base_asset, self._market_info.quote_asset,
                                   OrderType.LIMIT, TradeType.SELL, sell.size, sell.price)
            price = sell.price * (Decimal(1) + fee.percent)
            sell.price = market.c_quantize_order_price(self._market_info.trading_pair, price)

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

        active_buy_orders = [x.client_order_id for x in self.active_orders if x.is_buy]
        active_sell_orders = [x.client_order_id for x in self.active_orders if not x.is_buy]

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
            self._filled_buys_sells_balance += 1
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

        active_buy_orders = [x.client_order_id for x in self.active_orders if x.is_buy]
        active_sell_orders = [x.client_order_id for x in self.active_orders if not x.is_buy]

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
            self._filled_buys_sells_balance -= 1
            limit_order_record = self._sb_order_tracker.c_get_limit_order(market_info, order_id)
            self.log_with_clock(
                logging.INFO,
                f"({market_info.trading_pair}) Maker sell order {order_id} "
                f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
            )

    cdef bint c_is_within_tolerance(self, list current_prices, list proposal_prices):
        if len(current_prices) != len(proposal_prices):
            return False
        current_prices = sorted(current_prices)
        proposals = sorted(proposal_prices)
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
            active_sell_pricess = [Decimal(str(o.price)) for o in active_orders if not o.is_buy]
            proposal_buys = [buy.price for buy in proposal.buys]
            proposal_sells = [sell.price for sell in proposal.sells]
            if self.c_is_within_tolerance(active_buy_prices, proposal_buys) and \
                    self.c_is_within_tolerance(active_sell_pricess, proposal_sells):
                to_defer_canceling = True

        if not to_defer_canceling:
            for order in active_orders:
                self.c_cancel_order(self._market_info, order.client_order_id)
            # This is only for unit testing purpose as some test cases expect order creation to happen in the next tick.
            # In production, order creation always happens in another cycle as it first checks for no active orders.
            if self._create_timestamp <= self._current_timestamp:
                self._create_timestamp = self._current_timestamp + 0.1
        else:
            self.logger().info(f"Not cancelling active orders since difference between new order prices "
                               f"and current order prices is within "
                               f"{self._order_refresh_tolerance_pct:.2%} order_refresh_tolerance_pct")
            self.set_timers()

    cdef c_cancel_hanging_orders(self):
        cdef:
            object mid_price = self.mid_price
            list active_orders = self.active_orders
            list orders
            LimitOrder order
        for h_order_id in self._hanging_order_ids:
            orders = [o for o in active_orders if o.client_order_id == h_order_id]
            if orders and mid_price > 0:
                order = orders[0]
                if abs(order.price - mid_price)/mid_price >= self._hanging_orders_cancel_pct:
                    self.c_cancel_order(self._market_info, order.client_order_id)

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
                price_quote_str = [f"{buy.size.normalize()} {self._market_info.base_asset}, "
                                   f"{buy.price.normalize()} {self._market_info.quote_asset}"
                                   for buy in proposal.buys]
                self.logger().info(
                    f"({self._market_info.trading_pair}) Creating {len(proposal.buys)} bid orders "
                    f"at (Size, Price): {price_quote_str}"
                )
            for buy in proposal.buys:
                print(f"buying: {buy}")
                bid_order_id = self.c_buy_with_specific_market(
                    self._market_info,
                    buy.size,
                    order_type=self._limit_order_type,
                    price=buy.price,
                    expiration_seconds=expiration_seconds
                )
                orders_created = True
        if len(proposal.sells) > 0:
            if self._logging_options & self.OPTION_LOG_CREATE_ORDER:
                price_quote_str = [f"{sell.size.normalize()} {self._market_info.base_asset}, "
                                   f"{sell.price.normalize()} {self._market_info.quote_asset}"
                                   for sell in proposal.sells]
                self.logger().info(
                    f"({self._market_info.trading_pair}) Creating {len(proposal.sells)} ask "
                    f"orders at (Size, Price): {price_quote_str}"
                )
            for sell in proposal.sells:
                print(f"selling: {sell}")
                ask_order_id = self.c_sell_with_specific_market(
                    self._market_info,
                    sell.size,
                    order_type=self._limit_order_type,
                    price=sell.price,
                    expiration_seconds=expiration_seconds
                )
                orders_created = True
        if orders_created:
            self.set_timers()

    cdef set_timers(self):
        cdef double next_cycle = self._current_timestamp + self._order_refresh_time
        if self._create_timestamp <= self._current_timestamp:
            self._create_timestamp = next_cycle
        if self._cancel_timestamp <= self._current_timestamp:
            self._cancel_timestamp = min(self._create_timestamp, next_cycle)
