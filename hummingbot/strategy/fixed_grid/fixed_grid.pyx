import logging
import time
from decimal import Decimal
from math import (
    ceil,
    floor,
)
from typing import (
    Dict,
    List,
    Optional,
)

import numpy as np
import pandas as pd
import math 

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.events import OrderType, TradeType
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils import map_df_to_str
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_base import StrategyBase
from hummingbot.strategy.utils import order_age
from hummingbot.strategy.order_tracker import OrderTracker
from .data_types import (
    PriceSize,
    Proposal,
)

NaN = float("nan")
s_decimal_zero = Decimal(0)
s_decimal_neg_one = Decimal(-1)
pmm_logger = None


cdef class FixedGridStrategy(StrategyBase):
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
                    n_levels: int,
                    grid_price_ceiling: Decimal,
                    grid_price_floor: Decimal,
                    order_amount: Decimal,
                    start_order_spread: Decimal = Decimal(0.2),
                    order_refresh_time: float = 1800.0,
                    max_order_age: float = 1800.0,
                    order_refresh_tolerance_pct: Decimal = s_decimal_neg_one,
                    order_optimization_enabled: bool = False,
                    ask_order_optimization_depth: Decimal = s_decimal_zero,
                    bid_order_optimization_depth: Decimal = s_decimal_zero,
                    take_if_crossed: bool = False,
                    logging_options: int = OPTION_LOG_ALL,
                    status_report_interval: float = 900,
                    hb_app_notification: bool = False,
                    should_wait_order_cancel_confirmation = True,
                    ):
        if grid_price_ceiling < grid_price_floor:
            raise ValueError("Parameter grid_price_ceiling cannot be lower than grid_price_floor.")
        self._sb_order_tracker = OrderTracker()
        self._market_info = market_info
        self._start_order_spread = start_order_spread
        self._n_levels = n_levels
        self._grid_price_ceiling = grid_price_ceiling
        self._grid_price_floor = grid_price_floor
        self._order_amount = order_amount
        self._order_refresh_time = order_refresh_time
        self._max_order_age = max_order_age
        self._order_refresh_tolerance_pct = order_refresh_tolerance_pct
        self._order_optimization_enabled = order_optimization_enabled
        self._ask_order_optimization_depth = ask_order_optimization_depth
        self._bid_order_optimization_depth = bid_order_optimization_depth
        self._take_if_crossed = take_if_crossed
        self._hb_app_notification = hb_app_notification

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
        self._filled_order_delay = Decimal(1.0)
        
        self.c_add_markets([market_info.market])

        self._price_levels = []
        self._base_inv_levels = []
        self._quote_inv_levels = []
        self._quote_inv_levels_current_price = []
        self._current_level = -100
        self._grid_spread = (self._grid_price_ceiling - self._grid_price_floor)/(self._n_levels-1)
        self._inv_correct = True
        self._start_order_amount = s_decimal_zero
        self._start_order_buy = True


    def all_markets_ready(self):
        return all([market.ready for market in self._sb_markets])

    @property
    def market_info(self) -> MarketTradingPairTuple:
        return self._market_info

    @property
    def max_order_age(self) -> float:
        return self._max_order_age


    @property
    def ask_order_optimization_depth(self) -> Decimal:
        return self._ask_order_optimization_depth

    @property
    def bid_order_optimization_depth(self) -> Decimal:
        return self._bid_order_optimization_depth


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
    def n_levels(self) -> int:
        return self._n_levels

    @n_levels.setter
    def n_levels(self, value: int):
        self._n_levels = value
  
    @property
    def start_order_spread(self) -> Decimal:
        return self._start_order_spread

    @start_order_spread.setter
    def start_order_spread(self, value: Decimal):
        self._start_order_spread = value

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


    @property
    def grid_price_ceiling(self) -> Decimal:
        return self._grid_price_ceiling

    @grid_price_ceiling.setter
    def grid_price_ceiling(self, value: Decimal):
        self._grid_price_ceiling = value

    @property
    def grid_price_floor(self) -> Decimal:
        return self._grid_price_floor

    @grid_price_floor.setter
    def grid_price_floor(self, value: Decimal):
        self._grid_price_floor = value

    @property
    def price_levels(self) -> List:
        return self._price_levels

    @property
    def base_inv_levels(self) -> list:
        return self._base_inv_levels

    @property
    def quote_inv_levels(self) -> list:
        return self._quote_inv_levels

    @property
    def _quote_inv_levels_current_price(self) -> list:
        return self._quote_inv_levels_current_price

    @property
    def current_level(self) -> int:
        return self._current_level

    @property
    def grid_spread(self) -> Decimal:
        return self._grid_spread

    @property
    def inv_correct(self) -> bool:
        return self._inv_correct

    @property
    def start_order_amount(self) -> Decimal:
        return self._start_order_amount

    @property
    def start_order_buy(self) -> bool:
        return self._start_order_buy

    @property
    def base_asset(self) -> str:
        return self._market_info.base_asset

    @property
    def quote_asset(self) -> str:
        return self._market_info.quote_asset

    @property
    def trading_pair(self) -> str:
        return self._market_info.trading_pair


    def get_mid_price(self) -> Decimal:
        return self.c_get_mid_price()

    cdef object c_get_mid_price(self):
        cdef:
            object mid_price
        mid_price = self._market_info.get_mid_price()
        return mid_price


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
    def logging_options(self) -> int:
        return self._logging_options

    @logging_options.setter
    def logging_options(self, int64_t logging_options):
        self._logging_options = logging_options


    def grid_assets_df(self) -> pd.DataFrame:
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
        data.append(["Current %", f"{base_ratio:.1%}", f"{quote_ratio:.1%}"])
        df = pd.DataFrame(data=data)
        return df

    def active_orders_df(self) -> pd.DataFrame:
        market, trading_pair, base_asset, quote_asset = self._market_info
        price = self.get_mid_price()
        active_orders = self.active_orders
        no_sells = len([o for o in active_orders if not o.is_buy and o.client_order_id])
        active_orders.sort(key=lambda x: x.price, reverse=True)
        columns = ["Level", "Type", "Price", "Spread", "Amount (Orig)", "Amount (Adj)", "Age"]
        data = []
        lvl_buy, lvl_sell = 0, 0
        for idx in range(0, len(active_orders)):
            order = active_orders[idx]
  
            if order.is_buy:
                level = lvl_buy + 1
                lvl_buy += 1
            else:
                level = no_sells - lvl_sell
                lvl_sell += 1
            spread = 0 if price == 0 else abs(order.price - price)/price
            age = pd.Timestamp(order_age(order, self._current_timestamp), unit='s').strftime('%H:%M:%S')
	    # age = "n/a"
            # // indicates order is a paper order so 'n/a'. For real orders, calculate age.
            # if "//" not in order.client_order_id:
            #     age = pd.Timestamp(int(time.time()) - int(order.client_order_id[-16:])/1e6,
            #                        unit='s').strftime('%H:%M:%S')

           
            amount_orig = ""

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

    def grid_status_data_frame(self) -> pd.DataFrame:
        grid_data = []
        grid_columns = ["Parameter", "Value"]

        market, trading_pair, base_asset, quote_asset = self._market_info
        base_balance = float(market.get_balance(base_asset))
        quote_balance = float(market.get_balance(quote_asset)/self._price_levels[self._current_level])
                
        # grid_data.append(["Grid ceiling", self._grid_price_ceiling])
        # grid_data.append(["Grid floor", self._grid_price_floor])
        # grid_data.append(["Total grid levels", self._n_levels])
        grid_data.append(["Grid spread", round(self._grid_spread, 4)])
        grid_data.append(["Current grid level", self._current_level+1])
        grid_data.append([f"{base_asset} required", round(self._base_inv_levels[self._current_level], 4)])
        grid_data.append([f"{quote_asset} required in {base_asset}", round(self._quote_inv_levels_current_price[self._current_level], 4)])
        grid_data.append([f"{base_asset} balance", round(base_balance, 4)])
        grid_data.append([f"{quote_asset} balance in {base_asset}", round(quote_balance, 4)])
        grid_data.append(["Correct inventory balance", self._inv_correct])

        return pd.DataFrame(data=grid_data, columns=grid_columns).replace(np.nan, '', regex=True)


    def format_status(self) -> str:
        if not self._all_markets_ready:
            return "Market connectors are not ready."
        cdef:
            list lines = []
            list warning_lines = []
        warning_lines.extend(self.network_warning([self._market_info]))

        grid_df = map_df_to_str(self.grid_status_data_frame())
    
        lines.extend(["", "  Grid:"] + ["    " + line for line in grid_df.to_string(index=False).split("\n")])

        markets_df = map_df_to_str(self.market_status_data_frame([self._market_info]))
        lines.extend(["", "  Markets:"] + ["    " + line for line in markets_df.to_string(index=False).split("\n")])

        assets_df = map_df_to_str(self.grid_assets_df())
       
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
        
        for i in range(self._n_levels):
            self._price_levels.append(self._grid_price_floor + (i)*self._grid_spread)
            self._base_inv_levels.append((self._n_levels-i-1)*self._order_amount)
            self._quote_inv_levels.append(sum(self._price_levels[0:i])*self._order_amount)
            self._quote_inv_levels_current_price.append(self._quote_inv_levels[i]/self._price_levels[i])

        self._last_timestamp = timestamp

    cdef c_stop(self, Clock clock):
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

                # If grid level not yet set, find it. 
                if self._current_level is -100:
                    price = self._market_info.get_mid_price()
                    # Find level closest to market
                    min_diff = 1e8
                    for i in range(self._n_levels):
                        if min(min_diff, abs(self._price_levels[i]-price)) < min_diff:
                            min_diff = abs(self._price_levels[i]-price)
                            self._current_level = i
                            
                    self.logger().info(f"Initial level {self._current_level+1}")

                    if price > self._grid_price_ceiling:
                        self.logger().warning(f"WARNING: Current price is above grid ceiling")
              
                    elif price < self._grid_price_floor:
                        self.logger().warning(f"WARNING: Current price is below grid floor")
                 

                # Check if sufficient base and quote inventory are available according to current level
                market, trading_pair, base_asset, quote_asset = self._market_info
                base_balance = float(market.get_balance(base_asset))
                quote_balance = float(market.get_balance(quote_asset)/self._price_levels[self._current_level])
                # self.logger().info(f"Current level {self._current_level+1}")
                # self.logger().info(f"Base balance {base_balance}")
                # self.logger().info(f"Quote balance {quote_balance}")
                # self.logger().info(f"Base balance required {self._base_inv_levels[self._current_level]}")
                # self.logger().info(f"Quote balance required {self._quote_inv_levels[self._current_level]}")
                # self.logger().info(f"Price at current level {self._price_levels[self._current_level]}")
                # self.logger().info(f"Quote balance required in Base {self._quote_inv_levels_current_price[self._current_level]}")
                if base_balance < self._base_inv_levels[self._current_level]:
                    self._inv_correct = False
                    self.logger().warning(f"WARNING: Insuffient {base_asset} balance for grid bot. Will attempt to rebalance")
                    if base_balance + quote_balance < self._base_inv_levels[self._current_level] + self._quote_inv_levels_current_price[self._current_level]:
                        self.logger().warning(f"WARNING: Insuffient {base_asset} and {quote_asset} balance for grid bot. Unable to rebalance."
                                            f"Please add funds or change grid parameters")
                        return
                    else:
                        # Calculate additional base required with 5% tolerance 
                        base_required = (Decimal(self._base_inv_levels[self._current_level]) - Decimal(base_balance))*Decimal(1.05)
                        self._start_order_buy = True
                        self._start_order_amount = Decimal(base_required)                  
                elif quote_balance < self._quote_inv_levels_current_price[self._current_level]:
                    self._inv_correct = False
                    self.logger().warning(f"WARNING: Insuffient {quote_asset} balance for grid bot. Will attempt to rebalance")
                    if base_balance + quote_balance < self._base_inv_levels[self._current_level] + self._quote_inv_levels_current_price[self._current_level]:
                        self.logger().warning(f"WARNING: Insuffient {base_asset} and {quote_asset} balance for grid bot. Unable to rebalance."
                                            f"Please add funds or change grid parameters")
                        return
                    else:
                        # Calculate additional quote required with 5% tolerance 
                        quote_required = (Decimal(self._quote_inv_levels_current_price[self._current_level]) - Decimal(quote_balance))*Decimal(1.05)
                        self._start_order_buy = False
                        self._start_order_amount = Decimal(quote_required)
                else:
                    self._inv_correct = True

                if self._inv_correct is True:
                    # Create proposals for Grid
                    proposal = self.c_create_grid_proposal()
                else:
                    # Create rebalance proposal
                    proposal = self.c_create_rebalance_proposal()
                    # 2. Apply functions that modify orders price
                    self.c_apply_order_price_modifiers(proposal)
                if not self._take_if_crossed:
                    self.c_filter_out_takers(proposal)

            self.c_cancel_active_orders_on_max_age_limit()
            self.c_cancel_active_orders(proposal)
            if self.c_to_create_orders(proposal):
                self.c_execute_orders_proposal(proposal)
        finally:
            self._last_timestamp = timestamp

    cdef object c_create_grid_proposal(self):
        cdef:
            ExchangeBase market = self._market_info.market
            list buys = []
            list sells = []

        # Proposal will be created according to grid price levels
        for i in range(self._current_level):
            price = self._price_levels[i]
            price = market.c_quantize_order_price(self.trading_pair, price)
            size = self._order_amount
            size = market.c_quantize_order_amount(self.trading_pair, size)
            if size > 0:
                buys.append(PriceSize(price, size))

        for i in range(self._current_level+1,self._n_levels):
            price = self._price_levels[i]
            price = market.c_quantize_order_price(self.trading_pair, price)
            size = self._order_amount
            size = market.c_quantize_order_amount(self.trading_pair, size)
            if size > 0:
                sells.append(PriceSize(price, size))

        return Proposal(buys, sells)

    cdef object c_create_rebalance_proposal(self):
        cdef:
            ExchangeBase market = self._market_info.market
            list buys = []
            list sells = []

        # Proposal will be created according to start order spread.
        if self._start_order_buy is True:
            price = self.get_mid_price() * (Decimal("1") - self._start_order_spread)
            price = market.c_quantize_order_price(self.trading_pair, price)
            size = self._start_order_amount
            size = market.c_quantize_order_amount(self.trading_pair, size)
            self.logger().info(f"Placing buy order to rebalance; amount: {size}, price: {price}")
            if size > 0:
                buys.append(PriceSize(price, size))
        
        if self._start_order_buy is False:
            price = self.get_mid_price() * (Decimal("1") + self._start_order_spread)
            price = market.c_quantize_order_price(self.trading_pair, price)
            size = self._start_order_amount
            size = market.c_quantize_order_amount(self.trading_pair, size)
            self.logger().info(f"Placing sell order to rebalance; amount: {size}, price: {price}")
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


    cdef c_apply_order_price_modifiers(self, object proposal):
        if self._order_optimization_enabled:
            self.c_apply_order_optimization(proposal)



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
            ExchangeBase market = self._market_info.market
            
        if limit_order_record is None:
            return
        active_sell_ids = [x.client_order_id for x in self.active_orders if not x.is_buy]


        # delay order creation by filled_order_dalay (in seconds)
        if self._inv_correct is False:
            self._create_timestamp = self._current_timestamp + self._filled_order_delay
        else:
            self._create_timestamp = self._current_timestamp + self._order_refresh_time
        self._cancel_timestamp = min(self._cancel_timestamp, self._create_timestamp)

        self._filled_buys_balance += 1
        self._last_own_trade_price = limit_order_record.price

        self.log_with_clock(
            logging.INFO,
            f"({self.trading_pair}) Maker buy order {order_id} "
            f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
            f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
        )

        if self._inv_correct is True:
            # Set the new level
            self._current_level = self._current_level - 1
            # Add sell order above current level
            price = self._price_levels[self._current_level+1]
            price = market.c_quantize_order_price(self.trading_pair, price)
            size = self._order_amount
            size = market.c_quantize_order_amount(self.trading_pair, size)
            self.c_execute_orders_proposal(Proposal([], [PriceSize(price, size)]))

        self.notify_hb_app(
            f"Maker BUY order {limit_order_record.quantity} {limit_order_record.base_currency} @ "
            f"{limit_order_record.price} {limit_order_record.quote_currency} is filled."
        )

    cdef c_did_complete_sell_order(self, object order_completed_event):
        cdef:
            str order_id = order_completed_event.order_id
            LimitOrder limit_order_record = self._sb_order_tracker.c_get_limit_order(self._market_info, order_id)
            ExchangeBase market = self._market_info.market

        if limit_order_record is None:
            return
        active_buy_ids = [x.client_order_id for x in self.active_orders if x.is_buy]

        # delay order creation by filled_order_dalay (in seconds)
        if self._inv_correct is False:
            self._create_timestamp = self._current_timestamp + self._filled_order_delay
        else:
            self._create_timestamp = self._current_timestamp + self._order_refresh_time
        self._cancel_timestamp = min(self._cancel_timestamp, self._create_timestamp)

        self._filled_sells_balance += 1
        self._last_own_trade_price = limit_order_record.price

        self.log_with_clock(
            logging.INFO,
            f"({self.trading_pair}) Maker sell order {order_id} "
            f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
            f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
        )

        if self._inv_correct is True:
            # Set the new level
            self._current_level = self._current_level + 1
            # Add buy order above current level
            price = self._price_levels[self._current_level-1]
            price = market.c_quantize_order_price(self.trading_pair, price)
            size = self._order_amount
            size = market.c_quantize_order_amount(self.trading_pair, size)
            self.c_execute_orders_proposal(Proposal([PriceSize(price, size)], []))

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

    cdef c_cancel_active_orders_on_max_age_limit(self):
        """
        Cancels active non hanging orders if they are older than max age limit
        """
        cdef:
            list active_orders = self.active_orders

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
            list active_orders = self.active_orders
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
            for order in self.active_orders:
                    self.c_cancel_order(self._market_info, order.client_order_id)
        # else:
        #     self.set_timers()

   

    cdef bint c_to_create_orders(self, object proposal):
        non_hanging_orders_non_cancelled = [o for o in self.active_orders]
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
        number_of_pairs = 0

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

    