import datetime as dt
import glob
import logging
import os
from decimal import Decimal
from typing import List, Tuple

import numpy as np
import pandas as pd

from hummingbot.connector.exchange_base import ExchangeBase

from hummingbot.connector.exchange_base cimport ExchangeBase

from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.strategy.__utils__.trailing_indicators.instant_volatility import InstantVolatilityIndicator

from hummingbot.core.data_type.limit_order cimport LimitOrder

from hummingbot.core.event.events import BuyOrderCompletedEvent, SellOrderCompletedEvent
from hummingbot.strategy.cross_exchange_mining.cross_exchange_mining_config_map_pydantic import (
    CrossExchangeMiningConfigMap,
)
from hummingbot.strategy.strategy_base import StrategyBase

from .cross_exchange_mining_pair import CrossExchangeMiningPair
from .order_id_market_pair_tracker import OrderIDMarketPairTracker

# Cross exchange Mining script by bensmeaton@gmail.com
NaN = float("nan")
s_decimal_zero = Decimal(0)
s_decimal_nan = Decimal("nan")
s_logger = None


cdef class CrossExchangeMiningStrategy(StrategyBase):
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

    SHADOW_MAKER_ORDER_KEEP_ALIVE_DURATION = 60.0 * 15
    CANCEL_EXPIRY_DURATION = 60.0

    @classmethod
    def logger(cls):
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def init_params(self,
                    config_map: CrossExchangeMiningConfigMap,
                    market_pairs: List[CrossExchangeMiningPair],
                    status_report_interval: float = 900,
                    logging_options: int = OPTION_LOG_ALL,
                    hb_app_notification: bool = False,
                    ):
        """
        Initializes a cross exchange market making strategy object.

        :param config_map: Strategy configuration map
        :param market_pairs: list of cross exchange market pairs
        :param logging_options: bit field for what types of logging to enable in this strategy object
        :param hb_app_notification:
        """
        self._config_map = config_map
        self._market_pairs = {
            (market_pair.maker.market, market_pair.maker.trading_pair): market_pair
            for market_pair in market_pairs
        }
        self._maker_markets = set([market_pair.maker.market for market_pair in market_pairs])
        self._taker_markets = set([market_pair.taker.market for market_pair in market_pairs])
        self._all_markets_ready = False
        self._volatility_pct = 0
        self._volatility_timer = 0
        self._balance_timer = 0
        self._maker_side = True
        self._balance_flag = True
        self._tol_o = 0.1 / 100
        self._min_prof_adj = 0
        self._min_prof_adj_t = 0
        self._adjcount = []
        self._avg_vol = InstantVolatilityIndicator(sampling_length=self.volatility_buffer_size)
        self._anti_hysteresis_timers = {}
        self._order_fill_buy_events = {}
        self._order_fill_sell_events = {}
        self._suggested_price_samples = {}
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self._market_pair_tracker = OrderIDMarketPairTracker()
        self._last_conv_rates_logged = 0
        self._hb_app_notification = hb_app_notification

        self._maker_order_ids = []
        cdef:
            list all_markets = list(self._maker_markets | self._taker_markets)

        self.c_add_markets(all_markets)

    @property
    def order_amount(self):
        return self._config_map.order_amount

    @property
    def min_profitability(self):
        return self._config_map.min_profitability / Decimal("100")

    @property
    def avg_vol(self):
        return self._avg_vol

    @avg_vol.setter
    def avg_vol(self, indicator: InstantVolatilityIndicator):
        self._avg_vol = indicator

    @property
    def min_prof_adj_timer(self):
        return self._config_map.min_prof_adj_timer

    @property
    def volatility_buffer_size(self):
        return self._config_map.volatility_buffer_size

    @property
    def min_order_amount(self):
        return self._config_map.min_order_amount

    @property
    def rate_curve(self):
        return self._config_map.rate_curve

    @property
    def trade_fee(self):
        return self._config_map.trade_fee

    @property
    def status_report_interval(self):
        return self._status_report_interval

    @property
    def balance_adjustment_duration(self):
        return self._config_map.balance_adjustment_duration

    @property
    def min_prof_tol_high(self):
        return self._config_map.min_prof_tol_high / Decimal("100")

    @property
    def min_prof_tol_low(self):
        return self._config_map.min_prof_tol_low / Decimal("100")

    @property
    def slippage_buffer(self):
        return self._config_map.slippage_buffer / Decimal("100")

    @property
    def hanging_order_ids(self) -> List[str]:
        return self._hanging_order_ids

    @property
    def active_limit_orders(self) -> List[Tuple[ExchangeBase, LimitOrder]]:
        return [(ex, order) for ex, order in self._sb_order_tracker.active_limit_orders
                if order.client_order_id in self._maker_order_ids]

    def format_status(self) -> str:
        cdef:
            list lines = []
            list warning_lines = []
            dict tracked_maker_orders = {}
            LimitOrder typed_limit_order

        # Go through the currently open limit orders, and group them by market pair.
        active_orders_status = []
        limit_orders = list(self._sb_order_tracker.c_get_limit_orders().values())
        if limit_orders:
            for key in [elem for elem in limit_orders[0]]:
                active_orders_status.append(limit_orders[0][key])

        for market_pair in self._market_pairs.values():
            warning_lines.extend(self.network_warning([market_pair.maker, market_pair.taker]))

            markets_df = self.market_status_data_frame([market_pair.maker, market_pair.taker])
            lines.extend(["", "  Markets:"] +
                         ["    " + line for line in str(markets_df).split("\n")])

            assets_df = self.wallet_balance_data_frame([market_pair.maker, market_pair.taker])
            lines.extend(["", "  Assets:"] +
                         ["    " + line for line in str(assets_df).split("\n")])

            # See if there're any open orders.
            if active_orders_status:
                lines.extend(["", "  Active orders:"])
                for order in active_orders_status:
                    if order.is_buy:
                        lines.extend(["Current buy order of : " + str(order.trading_pair) + " with quantity: " + str(round(order.quantity, 5)) + " of " + str(order.base_currency) + " at price: " + str(round(order.price, 5))])
                    else:
                        lines.extend(["Current sell order of : " + str(order.trading_pair) + " with quantity: " + str(round(order.quantity, 5)) + " of " + str(order.base_currency) + " at price: " + str(round(order.price, 5))])
            else:
                lines.extend(["", "  No active maker orders."])

            warning_lines.extend(self.balance_warning([market_pair.maker, market_pair.taker]))

        if len(warning_lines) > 0:
            lines.extend(["", "  *** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    cdef volatility_rate(self, market_pair):
        cdef:
            ExchangeBase maker_market = market_pair.maker.market
            ExchangeBase taker_market = market_pair.taker.market
        mid_price = market_pair.maker.get_mid_price()
        self._avg_vol.add_sample(mid_price)
        vol_abs = Decimal((self._avg_vol.current_value / float(mid_price)) * 3)  # 3 sigma VOLATILITY ADJUSTMENT
        base = Decimal(0.00025)
        if self._volatility_timer + float(self.volatility_buffer_size) < self._current_timestamp or (base * round(vol_abs / base)) >= self._volatility_pct:
            self._volatility_pct = base * round(vol_abs / base)
            self._volatility_timer = self._current_timestamp

    cdef check_order(self, object market_pair, object active_order, object is_buy):
        cdef:
            ExchangeBase taker_market = market_pair.taker.market

        # Check current profitability for existing buy limit order
        if is_buy:
            taker_sell_price = taker_market.c_get_vwap_for_volume(market_pair.taker.trading_pair, False, active_order.quantity).result_price
            current_buy_price = active_order.price
            current_prof = 1 - (current_buy_price / taker_sell_price)
            # self.notify_hb_app("Check buy order, Current  price: " + str(round(active_order.price,5)) + " Current  qty: " + str(round(active_order.quantity,3)) + " can sell on taker for: " + str(round(taker_sell_price,5)) + " profitability is: " + str(round(current_prof,5)))
        # Check current profitability for existing sell limit order
        if not is_buy:
            taker_buy_price = taker_market.c_get_vwap_for_volume(market_pair.taker.trading_pair, True, active_order.quantity).result_price
            current_sell_price = active_order.price
            current_prof = 1 - (taker_buy_price / current_sell_price)
            # self.notify_hb_app("Check sell order, Current  price: " + str(round(active_order.price,5)) + " Current  qty: " + str(round(active_order.quantity,3)) + " can buy on taker for: " + str(round(taker_buy_price,5)) + " profitability is: " + str(round(current_prof,5)))
        # Check profitability is within tolerance around (Min profitability + volatility modifier + long term trade performance modifier)
        # If not cancel limit order
        prof_set = (self.min_profitability + self._volatility_pct + self._min_prof_adj)
        if current_prof < (prof_set - self.min_prof_tol_low) or current_prof > (prof_set + self.min_prof_tol_high):
            # self.notify_hb_app("Cancelling: " + str(current_prof) + " < " + str(prof_set - self.min_prof_tol_low) + " or > "+ str(prof_set + self.min_prof_tol_high))
            # market_trading_pair_tuple = self._sb_order_tracker.c_get_market_pair_from_order_id(active_order.client_order_id)
            market_trading_pair_tuple = self._sb_order_tracker.c_get_market_pair_from_order_id(active_order.client_order_id)
            if market_trading_pair_tuple:
                StrategyBase.c_cancel_order(self, market_trading_pair_tuple, active_order.client_order_id)
                StrategyBase.stop_tracking_limit_order(self, market_trading_pair_tuple, active_order.client_order_id)

    cdef set_order(self, object market_pair, object is_buy):
        cdef:
            ExchangeBase maker_market = market_pair.maker.market
            ExchangeBase taker_market = market_pair.taker.market

        maker_base_side_balance = maker_market.c_get_balance(market_pair.maker.base_asset)
        taker_base_side_balance = taker_market.c_get_balance(market_pair.taker.base_asset)
        try:
            # Average Price for buying order amount on maker market
            maker_buy_price = maker_market.c_get_vwap_for_volume(market_pair.maker.trading_pair, True, self.order_amount).result_price  # True = buy
        except ZeroDivisionError:
            maker_buy_price = taker_market.c_get_vwap_for_volume(market_pair.maker.trading_pair, True, self.order_amount).result_price  # True = buy
        try:
            # Average Price for buying order amount on taker market
            taker_buy_price = taker_market.c_get_vwap_for_volume(market_pair.taker.trading_pair, True, self.order_amount).result_price  # True = buy
        except ZeroDivisionError:
            taker_buy_price = maker_market.c_get_vwap_for_volume(market_pair.taker.trading_pair, True, self.order_amount).result_price  # True = buy
        # quantity of maker quote amount in base if sold on maker market
        maker_quote_side_balance_in_base = maker_market.c_get_available_balance(market_pair.maker.quote_asset) / maker_buy_price
        # quantity of taker quote amount in base if sold on taker market
        taker_quote_side_balance_in_base = taker_market.c_get_available_balance(market_pair.taker.quote_asset) / taker_buy_price

        var_list = [maker_base_side_balance, taker_base_side_balance, maker_buy_price, taker_buy_price, maker_quote_side_balance_in_base, taker_quote_side_balance_in_base]
        # self.notify_hb_app("Maker Buffer Price Sell Set: " + str(var_list))
        for item in var_list:
            if Decimal.is_nan(item):
                return s_decimal_nan, s_decimal_nan
        try:
            if not is_buy:  # Sell base on Maker side
                # Sell base on Maker side, take minimum of order amount in base, base amount on maker side and quote amount in base on taker side
                order_amount_maker_sell = min(float(taker_quote_side_balance_in_base), float(maker_base_side_balance), float(self.order_amount))
                if Decimal(order_amount_maker_sell) < self.min_order_amount:
                    return s_decimal_nan, s_decimal_nan
                # you are selling base asset on maker, using the actual order amount calculate the average price you would get if you bought that amount back on the taker side.
                taker_buy_price = taker_market.c_get_vwap_for_volume(market_pair.taker.trading_pair, True, Decimal(order_amount_maker_sell)).result_price
                # Therefore you can sell the amount for the price you would get if you bought on the taker market + min profitabilty
                maker_set_price_sell = taker_buy_price * (1 + (self.min_profitability + self._volatility_pct + self._min_prof_adj))
                # self.notify_hb_app("Looking to sell on maker, Can buy " + str(round(order_amount_maker_sell,2)) + " on taker for: " + str(round(taker_buy_price,5)) + " so sell on maker for: " + str(round(maker_set_price_sell,5)))
                return Decimal(maker_set_price_sell), Decimal(order_amount_maker_sell)

            if is_buy:  # buy base on Maker side
                # Buy base on Maker side
                # Buy base on Maker side, take minimum of order amount in base, quote amount on maker side in base and base amount on taker side
                order_amount_maker_buy = min(float(taker_base_side_balance), float(maker_quote_side_balance_in_base), float(self.order_amount))
                if Decimal(order_amount_maker_buy) < self.min_order_amount:
                    return s_decimal_nan, s_decimal_nan
                # you are buying base asset on maker, using the actual order amount calculate the average price you would get if you sold that amount back on the taker side.
                taker_sell_price = taker_market.c_get_vwap_for_volume(market_pair.taker.trading_pair, False, Decimal(order_amount_maker_buy)).result_price
                # Therefore you can sell the amount for the price you would get if you sold on the taker market - min profitabilty
                maker_set_price_buy = taker_sell_price * (1 - (self.min_profitability + self._volatility_pct + self._min_prof_adj))
                # self.notify_hb_app("Looking to buy on maker, Can sell " + str(round(order_amount_maker_buy,2)) + " on taker for: " + str(round(taker_sell_price,5)) + " so buy on maker for: " + str(round(maker_set_price_buy,5)))
                return Decimal(maker_set_price_buy), Decimal(order_amount_maker_buy)
        except Exception:
            return s_decimal_nan, s_decimal_nan

    cdef check_balance(self, object market_pair):
        cdef:
            ExchangeBase maker_market = market_pair.maker.market
            ExchangeBase taker_market = market_pair.taker.market

        # Script aims to continuosely check and reblance base assets on each exchange to maintain order amount across exchanges. This is also used to complete the XEMM trade after a limit order has been completed.
        maker_base_side_balance = maker_market.c_get_balance(market_pair.maker.base_asset)
        taker_base_side_balance = taker_market.c_get_balance(market_pair.taker.base_asset)
        self._balance_flag = False
        # self.notify_hb_app(str(taker_base_side_balance) +" " + str (maker_base_side_balance) + " " + str(self.order_amount))
        if (self.order_amount - self.min_order_amount) <= (taker_base_side_balance + maker_base_side_balance) <= (self.order_amount + self.min_order_amount):
            return

        try:
            maker_buy_price = maker_market.c_get_vwap_for_volume(market_pair.maker.trading_pair, True, self.order_amount).result_price  # True = buy
        except ZeroDivisionError:
            maker_buy_price = taker_market.c_get_vwap_for_volume(market_pair.maker.trading_pair, True, self.order_amount).result_price  # True = buy
        try:
            taker_buy_price = taker_market.c_get_vwap_for_volume(market_pair.taker.trading_pair, True, self.order_amount).result_price  # True = buy
        except ZeroDivisionError:
            taker_buy_price = maker_market.c_get_vwap_for_volume(market_pair.taker.trading_pair, True, self.order_amount).result_price  # True = buy

        maker_quote_side_balance_in_base = maker_market.c_get_available_balance(market_pair.maker.quote_asset) / maker_buy_price
        taker_quote_side_balance_in_base = taker_market.c_get_available_balance(market_pair.taker.quote_asset) / taker_buy_price

        var_list = [maker_base_side_balance, taker_base_side_balance, maker_buy_price, taker_buy_price, maker_quote_side_balance_in_base, taker_quote_side_balance_in_base]

        for item in var_list:
            if Decimal.is_nan(item):
                return

        check_mat = []
        buytaker = False
        selltaker = False

        if taker_base_side_balance + maker_base_side_balance < (self.order_amount - self.min_order_amount):  # Need to Buy taker base balance as maker side does not balance
            taker_qty = Decimal.min((self.order_amount - (taker_base_side_balance + maker_base_side_balance)), taker_quote_side_balance_in_base)
            if taker_qty:
                taker_price = taker_market.c_get_vwap_for_volume(market_pair.taker.trading_pair, True, Decimal(taker_qty)).result_price
                # self.notify_hb_app(str(taker_qty) + " t " + str(taker_price))
                if taker_qty > self.min_order_amount:
                    buytaker = True
                    check_mat = [False, market_pair, True, taker_qty, taker_price]

        if taker_base_side_balance + maker_base_side_balance > (self.order_amount + self.min_order_amount):  # Need to Sell taker base balance as maker side does not balance
            taker_qty = Decimal.min(((taker_base_side_balance + maker_base_side_balance) - self.order_amount), taker_base_side_balance)
            if taker_qty:
                taker_price = taker_market.c_get_vwap_for_volume(market_pair.taker.trading_pair, False, Decimal(taker_qty)).result_price
                if taker_qty > self.min_order_amount:
                    selltaker = True
                    check_mat = [False, market_pair, False, taker_qty, taker_price]

        if maker_base_side_balance + taker_base_side_balance < (self.order_amount - self.min_order_amount):  # Need to Buy maker base balance as taker side does not balance
            maker_qty = Decimal.min((self.order_amount - (maker_base_side_balance + taker_base_side_balance)), maker_quote_side_balance_in_base)
            if maker_qty:
                maker_price = maker_market.c_get_vwap_for_volume(market_pair.maker.trading_pair, True, Decimal(maker_qty)).result_price
                # self.notify_hb_app(str(maker_qty) + " m " + str(maker_price))
                if maker_qty > self.min_order_amount:
                    if ((maker_price < taker_price and buytaker) or not buytaker):
                        check_mat = [True, market_pair, True, maker_qty, maker_price]

        if maker_base_side_balance + taker_base_side_balance > (self.order_amount + self.min_order_amount):  # Need to Sell maker base balance as taker side does not balance
            maker_qty = Decimal.min(((maker_base_side_balance + taker_base_side_balance) - self.order_amount), maker_base_side_balance)
            if maker_qty:
                maker_price = maker_market.c_get_vwap_for_volume(market_pair.maker.trading_pair, False, Decimal(maker_qty)).result_price
                if maker_qty > self.min_order_amount:
                    if ((maker_price > taker_price and selltaker) or not selltaker):
                        check_mat = [True, market_pair, False, maker_qty, maker_price]
        # self.notify_hb_app(str(check_mat))
        if check_mat:
            self._balance_timer = self._current_timestamp + self.balance_adjustment_duration
            self._balance_flag = True
            return check_mat
        else:
            return

    cdef c_tick(self, double timestamp):
        """
        Clock tick entry point.

        :param timestamp: current tick timestamp
        """
        StrategyBase.c_tick(self, timestamp)
        # Perform clock tick with the market pair tracker.
        self._market_pair_tracker.c_tick(timestamp)

        cdef:
            list active_limit_orders = self.active_limit_orders
            LimitOrder limit_order
            bint has_active_bid = False
            bint has_active_ask = False

        if not self._all_markets_ready:
            self._all_markets_ready = all([market.ready for market in self._sb_markets])
            if not self._all_markets_ready:
                # Markets not ready yet. Don't do anything.
                return
            else:
                # Markets are ready, ok to proceed.
                if self.OPTION_LOG_STATUS_REPORT:
                    self.logger().info("Markets are ready. Trading started.")

        for market_pair in self._market_pairs.values():
            buy_orders = []
            sell_orders = []
            active_orders = []

            # Check for active limit orders and create buy and sell order lists
            limit_orders = list(self._sb_order_tracker.c_get_limit_orders().values())
            if limit_orders:
                for key in [elem for elem in limit_orders[0]]:
                    active_orders.append(limit_orders[0][key])
                    if limit_orders[0][key].is_buy:
                        buy_orders.append(limit_orders[0][key])
                    else:
                        sell_orders.append(limit_orders[0][key])

            self.volatility_rate(market_pair)
            # If there are buy orders check buy orders
            if buy_orders:
                for active_buy_order in buy_orders:
                    self.check_order(market_pair, active_buy_order, True)

            # If there are sell orders check sell orders
            if sell_orders:
                for active_sell_order in sell_orders:
                    self.check_order(market_pair, active_sell_order, False)

            # If there are no buy orders set them
            if not buy_orders:
                buyprice, buysize = self.set_order(market_pair, True)
                if not Decimal.is_nan(buyprice):
                    if not self._balance_flag:
                        self.c_place_order(market_pair, True, True, buysize, buyprice, True)

            # If there are no sell orders set them
            if not sell_orders:
                sellprice, sellsize = self.set_order(market_pair, False)
                if not Decimal.is_nan(sellprice):
                    if not self._balance_flag:
                        self.c_place_order(market_pair, False, True, sellsize, sellprice, True)

            # Balance base across exchanges
            if self._current_timestamp > self._balance_timer:
                bal_check = self.check_balance(market_pair)
                if bal_check:
                    # clear any existing trades to prioritise balance
                    self.cancel_all_trades(active_orders)
                    if bal_check[2]:  # buy order
                        self.c_place_order(bal_check[1], True, bal_check[0], bal_check[3], bal_check[4] * (1 + self.slippage_buffer), False)
                        return
                    else:  # sell order
                        self.c_place_order(bal_check[1], False, bal_check[0], bal_check[3], bal_check[4] * (1 - self.slippage_buffer), False)
                        return

            if self._current_timestamp > self._min_prof_adj_t:
                self._min_prof_adj = Decimal(self.adjust_profitability_lag(market_pair))
                self._min_prof_adj_t = self._current_timestamp + self.min_prof_adj_timer
                self.cancel_all_trades(active_orders)
                self.logger().info("Adjusted Min Profitability from previous trades")

    cdef adjust_profitability_lag(self, object market_pair):
        cdef:
            ExchangeBase maker_market = market_pair.maker.market
            ExchangeBase taker_market = market_pair.taker.market

        feea1 = float(self.trade_fee)
        min_prof = 0
        rate_curve = float(self.rate_curve)
        try:
            fileloc = max(glob.glob('data/trades_*.csv'), key=os.path.getmtime)
        except Exception:
            return 0
        df = pd.read_csv(fileloc)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit='ms')
        # Show last 24 hour results
        df = df[df['timestamp'] >= (dt.datetime.now() - dt.timedelta(hours=24))].reset_index(drop=True)
        an_1 = []
        while (len(df) > 0):
            try:
                start = df['timestamp'][0] - pd.Timedelta(seconds=1)
                stop = df['timestamp'][0] + pd.Timedelta(minutes=1)
                mattime = df.loc[(df['timestamp'] > start) & (df['timestamp'] < stop)].reindex(columns = ['order_id', 'symbol', 'price', 'amount', 'timestamp', 'trade_type']).reset_index(drop=True)
                mattime = mattime.loc[(mattime['price'] < mattime['price'][0] * 1.1) & (mattime['price'] > mattime['price'][0] * 0.9)]
                mattime = mattime.loc[(mattime['trade_type'] == mattime['trade_type'][0])].reset_index(drop=True)
                if mattime['trade_type'][0] == 'BUY':
                    sidex = 'SELL'
                else:
                    sidex = 'BUY'
                tattime = df.loc[(df['timestamp'] > start) & (df['timestamp'] < stop)].reindex(columns = ['order_id', 'symbol', 'price', 'amount', 'timestamp', 'trade_type']).reset_index(drop=True)
                tattime = tattime.loc[(tattime['price'] < mattime['price'][0] * 1.1) & (tattime['price'] > mattime['price'][0] * 0.9)]
                tattime = tattime.loc[(tattime['trade_type'] == sidex)].reset_index(drop=True)
                df = df.iloc[len(mattime):].reset_index(drop=True)
                df = df.iloc[len(tattime):].reset_index(drop=True)
                s_id = str(tattime['order_id'][0]) + str(mattime['order_id'][0])
                s_msum = mattime['amount'].astype(float).sum()
                s_tsum = tattime['amount'].astype(float).sum()
                s_mside = mattime['trade_type'][0]
                s_tside = tattime['trade_type'][0]
                if s_msum < s_tsum * 0.8 or s_msum > s_tsum * 1.2:
                    tattime = (tattime.iloc[(tattime['amount'] - s_msum).abs().argsort()[:1]]).reset_index(drop=True)
                    s_tsum = tattime['amount'].astype(float).sum()
                s_pmak = 0
                for x in range(len(mattime)):
                    s_pmak += float(mattime['price'][x]) * float(mattime['amount'][x])
                s_pmak = s_pmak / s_msum
                s_ptak = 0
                for y in range(len(tattime)):
                    s_ptak += float(tattime['price'][y]) * float(tattime['amount'][y])
                s_ptak = s_ptak / s_tsum
                sym_q = mattime['symbol'][0].split('-')[1]
                if mattime['trade_type'][0] == 'BUY':
                    s_per = ((s_ptak - s_pmak) / ((s_ptak + s_pmak) / 2)) * 100
                if mattime['trade_type'][0] == 'SELL':
                    s_per = ((s_pmak - s_ptak) / ((s_ptak + s_pmak) / 2)) * 100
                base = ((s_ptak + s_pmak) / 2) * ((s_msum + s_tsum) / 2) * ((s_per - feea1) / 100)
                per_am = (s_per - feea1) * ((s_msum + s_tsum) / 2)
                per_am_sum = ((s_msum + s_tsum) / 2)
                an_1.append([s_id, (tattime['timestamp'][0] - mattime['timestamp'][0]) / np.timedelta64(1, 's'), mattime['symbol'][0], s_msum, s_tsum, s_mside, s_tside, s_pmak, s_ptak, s_per, s_per - feea1, base, per_am, per_am_sum])
            except Exception:
                pass
        an_final = pd.DataFrame(an_1, columns = ['id', 'time', 'symbol', 'Total_Maker', 'Total_Taker', 'Maker_Side', 'Taker_Side', 'Price_Maker', 'Price_Taker', 'Percentage', 'Percentage_+_Fee', 'cost (quote)', 'per_am', 'per_am_sum'])
        if len(an_final) == 0:
            self.logger().info("No trade records within the past 24 hours found within datafile")
            return 0
        per_am = an_final['per_am'].sum() / an_final['per_am_sum'].sum()
        sum_base = an_final['cost (quote)'].sum()
        time_av = an_final['time'].mean()
        prof_adj = (- (per_am * rate_curve)**3 + min_prof) / 100
        self.logger().info(f"Percentage for trades over the last 24 Hours: {round(per_am, 3)}, No trades: {round(len(an_final))}, Min Profitability: {round(self.min_profitability + Decimal(prof_adj), 5)}, Profit: {round(sum_base, 2)} {sym_q}, Mean time to balance after fill: {round(time_av, 2)} s")
        return prof_adj

    cdef str c_place_order(self, object market_pair, bint is_buy, bint is_maker, object amount, object price, bint is_limit):

        cdef:
            str order_id
            object market_info = market_pair.maker if is_maker else market_pair.taker
            object order_type = market_info.market.get_maker_order_type() if is_limit else market_info.market.get_taker_order_type()

        amount = amount * Decimal(1 - self._tol_o)
        if is_buy:
            order_id = StrategyBase.c_buy_with_specific_market(self, market_info, amount, order_type=order_type, price=price, expiration_seconds=NaN)
        else:
            order_id = StrategyBase.c_sell_with_specific_market(self, market_info, amount, order_type=order_type, price=price, expiration_seconds=NaN)
        # market_trading_pair_tuple = self._sb_order_tracker.c_get_market_pair_from_order_id(order_id)
        mid_price = market_info.get_mid_price()
        if is_limit:
            StrategyBase.start_tracking_limit_order(self, market_info, order_id, is_buy, price, amount)
            self.logger().info(f"Maker Order Created: {market_pair.maker.trading_pair}, Amount: {round(amount, 3)}, Price: {round(price, 3)}, Min profitability: {self.min_profitability} + {round(self._volatility_pct, 5)} + {round(self._min_prof_adj, 5)}, % from Mid Market: {round(((max(price, mid_price)/min(price, mid_price))-1)*100, 3)} ")
        else:
            self.logger().info(f"Taker Order Created: {market_pair.maker.trading_pair}, Amount: {round(amount, 3)}, Price: {round(price, 3)}, Min profitability: {self.min_profitability} + {round(self._volatility_pct, 5)} + {round(self._min_prof_adj, 5)}, % from Mid Market: {round(((max(price, mid_price)/min(price, mid_price))-1)*100, 3)} ")
            # self.notify_hb_app("Order Created: " + str(market_pair.maker.trading_pair) +" Amount: " + str(amount) + " Price: " + str(price) + " Min profitability: " + str(self.min_profitability) + " + " + str(self._volatility_pct) + " + " + str(self._min_prof_adj))
        return order_id

    def notify_hb_app(self, msg: str):
        if self._hb_app_notification:
            super().notify_hb_app(msg)

    def cancel_all_trades(self, active_orders):
        for active_order in active_orders:
            market_trading_pair_tuple = self._sb_order_tracker.c_get_market_pair_from_order_id(active_order.client_order_id)
            if market_trading_pair_tuple:
                StrategyBase.c_cancel_order(self, market_trading_pair_tuple, active_order.client_order_id)
                StrategyBase.stop_tracking_limit_order(self, market_trading_pair_tuple, active_order.client_order_id)

    def did_complete_buy_order(self, order_completed_event: BuyOrderCompletedEvent):
        """
        Output log message when a bid order (on maker side or taker side) is completely taken.
        :param order_completed_event: event object
        """
        order_id = order_completed_event.order_id
        market_pair = self._market_pair_tracker.get_market_pair_from_order_id(order_id)
        if market_pair is not None:
            limit_order_record = self._sb_order_tracker.get_limit_order(market_pair.maker, order_id)
            self.notify_hb_app("Buy Order Completed: " + str(market_pair.maker.trading_pair) + " Quantity: " + str(limit_order_record.quantity) + " of " + str(limit_order_record.base_currency) + " Price: " + str(limit_order_record.price))

    def did_complete_sell_order(self, order_completed_event: SellOrderCompletedEvent):
        """
        Output log message when a ask order (on maker side or taker side) is completely taken.
        :param order_completed_event: event object
        """
        order_id = order_completed_event.order_id
        market_pair = self._market_pair_tracker.get_market_pair_from_order_id(order_id)

        if market_pair is not None:
            limit_order_record = self._sb_order_tracker.get_limit_order(market_pair.maker, order_id)
            self.notify_hb_app("Sell Order Completed: " + str(market_pair.maker.trading_pair) + " Quantity: " + str(limit_order_record.quantity) + " of " + str(limit_order_record.base_currency) + " Price: " + str(limit_order_record.price))
