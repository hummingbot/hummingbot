from decimal import Decimal
import logging
import pandas as pd
import numpy as np
import statistics
from typing import (
    List,
    Dict,
)
from math import (
    floor,
    ceil,
    isnan
)
import time
import datetime
import os
from hummingbot.core.clock cimport Clock
from hummingbot.core.event.events import TradeType
from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.event.events import OrderType

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_base import StrategyBase
from hummingbot.client.config.global_config_map import global_config_map

from ..order_tracker cimport OrderTracker
from ..__utils__.trailing_indicators.average_volatility import AverageVolatilityIndicator


NaN = float("nan")
s_decimal_zero = Decimal(0)
s_decimal_neg_one = Decimal(-1)
s_decimal_one = Decimal(1)
pmm_logger = None


cdef class BBOStrategy(StrategyBase):
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
                 order_amount: Decimal,
                 filled_order_delay: float = 60.0,
                 logging_options: int = OPTION_LOG_ALL,
                 status_report_interval: float = 900,
                 hb_app_notification: bool = False,
                 debug_csv_path: str = '',
                 volatility_days: int = 100,
                 entry_band: Decimal = Decimal('3'),
                 exit_band: Decimal = Decimal('1'),
                 is_debug: bool = True,
                 ):
        super().__init__()
        self._sb_order_tracker = OrderTracker()
        self._market_info = market_info
        self._order_amount = order_amount
        self._filled_order_delay = filled_order_delay
        self._hb_app_notification = hb_app_notification

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
        self._debug_csv_path = debug_csv_path
        self._is_debug = is_debug
        self._last_update_time = 0
        self._candle_days = volatility_days
        self._entry_band = entry_band
        self._exit_band = exit_band
        try:
            if self._is_debug:
                os.unlink(self._debug_csv_path)
        except FileNotFoundError:
            pass

    def all_markets_ready(self):
        return all([market.ready for market in self._sb_markets])

    @property
    def market_info(self) -> MarketTradingPairTuple:
        return self._market_info

    @property
    def order_amount(self) -> Decimal:
        return self._order_amount

    @order_amount.setter
    def order_amount(self, value: Decimal):
        self._order_amount = value

    @property
    def base_asset(self):
        return self._market_info.base_asset

    @property
    def quote_asset(self):
        return self._market_info.quote_asset

    @property
    def trading_pair(self):
        return self._market_info.trading_pair

    def get_price(self) -> float:
        return self.get_mid_price()

    def get_last_price(self) -> float:
        return self._market_info.get_last_price()

    def get_mid_price(self) -> float:
        return self.c_get_mid_price()

    cdef object c_get_mid_price(self):
        return self._market_info.get_mid_price()

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

    @property
    def order_tracker(self):
        return self._sb_order_tracker

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
        no_sells = len([o for o in active_orders if not o.is_buy and o.client_order_id])
        active_orders.sort(key=lambda x: x.price, reverse=True)
        columns = ["Level", "Type", "Price", "Spread", "Amount (Orig)", "Amount (Adj)", "Age"]
        data = []
        lvl_buy, lvl_sell = 0, 0
        for idx in range(0, len(active_orders)):
            order = active_orders[idx]
            spread = 0 if price == 0 else abs(order.price - price)/price
            age = "n/a"
            # // indicates order is a paper order so 'n/a'. For real orders, calculate age.
            if "//" not in order.client_order_id:
                age = pd.Timestamp(int(time.time()) - int(order.client_order_id[-16:])/1e6,
                                   unit='s').strftime('%H:%M:%S')
            amount_orig = self._order_amount
            data.append([
                "",
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

        assets_df = self.pure_mm_assets_df(True)
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

        lines.extend(["", f"  Strategy parameters:",
                          f"    entry_price= {self._entry_price}",
                          f"    exit_price= {self._exit_price}"])

        warning_lines.extend(self.balance_warning([self._market_info]))

        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    # The following exposed Python functions are meant for unit tests
    # ---------------------------------------------------------------
    
    def cancel_order(self, order_id: str):
        return self.c_cancel_order(self._market_info, order_id)

    # ---------------------------------------------------------------

    cdef c_start(self, Clock clock, double timestamp):
        StrategyBase.c_start(self, clock, timestamp)
        self._last_timestamp = timestamp
        # start tracking any restored limit order
        restored_order_ids = self.c_track_restored_orders(self.market_info)
        self._candles = self._market_info.market.get_historical(self._market_info.trading_pair, self._candle_days)

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

            # Make sure we have the historical candle data
            if not self.c_is_algorithm_ready():
                self._candles = self._market_info.market.get_historical(self._market_info.trading_pair, self._candle_days)
                return            

            # Run an update once a minute
            if (timestamp - self._last_update_time) > 60.0:

                # Get the most recent data
                self._candles = self._market_info.market.get_historical(self._market_info.trading_pair, self._candle_days)
                self._last_update_time = timestamp

                # Grab the inital candle days worth of closes
                closes = list(map(lambda x: x.close, self._candles))

                # Get the mean and standard deviation of the closes
                mean = statistics.mean(closes)
                stdev = statistics.stdev(closes)

                # Determine the entry and exit points
                self._entry_price = mean + self._entry_band * stdev
                self._exit_price = mean - self._exit_band * stdev

                self.logger().info(f"mean: {mean} Stdev: {stdev} Entry: {self._entry_price} Exit: {self._exit_price}")

            # How much of the base asset do we currently have?
            market = self._market_info.market
            trading_pair = self._market_info.trading_pair
            base_asset = self._market_info.base_asset
            base_asset_amount = market.get_balance(base_asset)

            # If the price is lower than or equal to the exit price, we should liquidate all of the base asset
            price = self.get_price()
            quantized_amount = market.quantize_order_amount(trading_pair, Decimal(str(base_asset_amount)))
            if quantized_amount > 0 and price <= self._exit_price and len(self.active_sells) == 0:
                # create a sell order
                self.logger().info(f"All of the base asset is being liquidated via market order")
                self.c_sell_with_specific_market(
                    self._market_info,
                    quantized_amount
                )
                return

            # If the price is greater than or equal to the entry price, we should buy up to the order amount,
            # if there is enough quote, of the base
            needed = self._order_amount - base_asset_amount
            quote_asset = self._market_info.quote_asset
            quote_asset_amount = market.get_balance(quote_asset)
            quote_asset_amount_in_base = quote_asset_amount / price
            quantized_amount = market.quantize_order_amount(trading_pair, Decimal(str(min(needed,quote_asset_amount_in_base))))
            if quantized_amount > 0 and price >= self._entry_price and len(self.active_buys) == 0:
                # create a buy order
                self.logger().info(f"Buying {needed} of the base asset with a market order")
                self.c_buy_with_specific_market(
                    self._market_info,
                    quantized_amount
                )
                return

            # Otherwise we do nothing

        finally:
            self._last_timestamp = timestamp

    cdef bint c_is_algorithm_ready(self):
        return self._candles

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

        # delay order creation by filled_order_delay (in seconds)
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

        # delay order creation by filled_order_delay (in seconds)
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
        self.notify_hb_app(
            f"Maker SELL order {limit_order_record.quantity} {limit_order_record.base_currency} @ "
            f"{limit_order_record.price} {limit_order_record.quote_currency} is filled."
        )

    # Cancel active orders
    # Return value: whether order cancellation is deferred.
    cdef c_cancel_active_orders(self, object proposal):
        if self._cancel_timestamp > self._current_timestamp:
            return
        if not global_config_map.get("0x_active_cancels").value:
            if ((self._market_info.market.name in self.RADAR_RELAY_TYPE_EXCHANGES) or
                    (self._market_info.market.name == "bamboo_relay" and not self._market_info.market.use_coordinator)):
                return

        cdef:
            list active_orders = self.active_orders
            list active_buy_prices = []
            list active_sells = []
            bint to_defer_canceling = False
        if len(active_orders) == 0:
            return
        if proposal is not None:
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
            self.set_timers()

    def notify_hb_app(self, msg: str):
        if self._hb_app_notification:
            from hummingbot.client.hummingbot_application import HummingbotApplication
            HummingbotApplication.main_application()._notify(msg)
