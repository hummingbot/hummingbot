# distutils: language=c++
from decimal import Decimal
import logging
import math
import pandas as pd
from typing import (
    List,
    Tuple,
    Optional,
    Dict
)

from hummingbot.client.performance import smart_round
from hummingbot.core.clock cimport Clock
from hummingbot.logger import HummingbotLogger
from hummingbot.core.event.event_listener cimport EventListener
from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.event.events import (
    OrderType,
    TradeType
)

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_base import StrategyBase

from libc.stdint cimport int64_t
from hummingbot.core.data_type.order_book cimport OrderBook
from datetime import datetime

NaN = float("nan")
s_decimal_zero = Decimal(0)
days2timestamp = (lambda x: x)
ds_logger = None

cdef class DCATradeStrategy(StrategyBase):
    OPTION_LOG_NULL_ORDER_SIZE = 1 << 0
    OPTION_LOG_REMOVING_ORDER = 1 << 1
    OPTION_LOG_ADJUST_ORDER = 1 << 2
    OPTION_LOG_CREATE_ORDER = 1 << 3
    OPTION_LOG_MAKER_ORDER_FILLED = 1 << 4
    OPTION_LOG_STATUS_REPORT = 1 << 5
    OPTION_LOG_MAKER_ORDER_HEDGED = 1 << 6
    OPTION_LOG_ALL = 0x7fffffffffffffff
    CANCEL_EXPIRY_DURATION = 60.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global ds_logger
        if ds_logger is None:
            ds_logger = logging.getLogger(__name__)
        return ds_logger

    def __init__(self,
                 market_infos: List[MarketTradingPairTuple],
                 order_type: str = "market",
                 is_buy: bool = True,
                 days_period: int = 30,
                 num_individual_orders: int = 6,
                 order_amount: Decimal = Decimal("1.0"),
                 logging_options: int = OPTION_LOG_ALL,
                 status_report_interval: float = 5):
        """
        :param market_infos: list of market trading pairs
        :param days_period: how many days to wait between placing trades
        :param order_amount: qty of the order to place
        :param logging_options: select the types of logs to output
        :param num_individual_orders: how many individual orders to split the order into
        :param status_report_interval: how many days to report network connection related warnings, if any
        """

        if len(market_infos) < 1:
            raise ValueError(f"market_infos must not be empty.")

        super().__init__()
        self._market_infos = {
            (market_info.market, market_info.trading_pair): market_info
            for market_info in market_infos
        }
        self._all_markets_ready = False
        self._place_orders = True
        self._logging_options = logging_options
        self._status_report_interval = status_report_interval
        self._num_individual_orders = num_individual_orders
        self._days_period = days_period
        self._quantity_remaining = order_amount
        self._time_to_cancel = {}
        self._order_amount = order_amount
        self._first_order = True

        cdef:
            set all_markets = set([market_info.market for market_info in market_infos])

        self.c_add_markets(list(all_markets))

    @property
    def active_bids(self) -> List[Tuple[ExchangeBase, LimitOrder]]:
        return self._sb_order_tracker.active_bids

    @property
    def active_asks(self) -> List[Tuple[ExchangeBase, LimitOrder]]:
        return self._sb_order_tracker.active_asks

    @property
    def active_limit_orders(self) -> List[Tuple[ExchangeBase, LimitOrder]]:
        return self._sb_order_tracker.active_limit_orders

    @property
    def in_flight_cancels(self) -> Dict[str, float]:
        return self._sb_order_tracker.in_flight_cancels

    @property
    def market_info_to_active_orders(self) -> Dict[MarketTradingPairTuple, List[LimitOrder]]:
        return self._sb_order_tracker.market_pair_to_active_orders

    @property
    def logging_options(self) -> int:
        return self._logging_options

    @logging_options.setter
    def logging_options(self, int64_t logging_options):
        self._logging_options = logging_options

    @property
    def place_orders(self):
        return self._place_orders


    async def format_status(self) -> str:
        """
        Returns a status string formatted to display nicely on terminal. The strings composes of 4 parts: markets,
        assets, profitability and warnings(if any).
        """

        if self._arb_proposals is None:
            return "  The strategy is not ready, please try again later."
        # active_orders = self.market_info_to_active_orders.get(self._market_info, [])
        columns = ["Exchange", "Market", "Sell Price", "Buy Price", "Mid Price"]
        data = []
        for market_info in [self._market_info_1, self._market_info_2]:
            market, trading_pair, base_asset, quote_asset = market_info
            buy_price = await market.get_quote_price(trading_pair, True, self._order_amount)
            sell_price = await market.get_quote_price(trading_pair, False, self._order_amount)

            # check for unavailable price data
            buy_price = smart_round(Decimal(str(buy_price)), 8) if buy_price is not None else '-'
            sell_price = smart_round(Decimal(str(sell_price)), 8) if sell_price is not None else '-'
            mid_price = smart_round(((buy_price + sell_price) / 2), 8) if '-' not in [buy_price, sell_price] else '-'

            data.append([
                market.display_name,
                trading_pair,
                sell_price,
                buy_price,
                mid_price
            ])
        markets_df = pd.DataFrame(data=data, columns=columns)
        lines = []
        lines.extend(["", "  Markets:"] + ["    " + line for line in markets_df.to_string(index=False).split("\n")])

        assets_df = self.wallet_balance_data_frame([self._market_info_1, self._market_info_2])
        lines.extend(["", "  Assets:"] +
                     ["    " + line for line in str(assets_df).split("\n")])

        warning_lines = self.network_warning([self._market_info_1])
        warning_lines.extend(self.network_warning([self._market_info_2]))
        warning_lines.extend(self.balance_warning([self._market_info_1]))
        warning_lines.extend(self.balance_warning([self._market_info_2]))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    cdef c_did_complete_buy_order(self, object order_completed_event):
        """
        Output log for completed buy order.

        :param order_completed_event: Order completed event
        """
        cdef:
            str order_id = order_completed_event.order_id
            object market_info = self._sb_order_tracker.c_get_market_pair_from_order_id(order_id)

        if market_info is not None:
            market_order_record = self._sb_order_tracker.c_get_market_order(market_info, order_id)
            self.log_with_clock(
                logging.INFO,
                f"({market_info.trading_pair}) Market buy order {order_id} "
                f"({market_order_record.amount} {market_order_record.base_asset}) has been filled."
            )


    cdef c_start(self, Clock clock, double timestamp):
        StrategyBase.c_start(self, clock, timestamp)
        self.logger().info(f"Waiting for {self._days_period} to place orders")
        self._previous_timestamp = timestamp
        self._last_timestamp = timestamp

    cdef c_tick(self, double timestamp):
        """
        Clock tick entry point.

        For the DCA strategy, this function simply checks if enough days have been passed since the last trade, if yes 
        then delegates the processing of each market info to c_process_market().

        :param timestamp: current tick timestamp
        """
        StrategyBase.c_tick(self, timestamp)
        cdef:
            int64_t current_tick = <int64_t>(timestamp // days2timestamp(self._status_report_interval))
            int64_t last_tick = <int64_t>(self._last_timestamp // days2timestamp(self._status_report_interval))
            bint should_report_warnings = ((current_tick > last_tick) and
                                           (self._logging_options & self.OPTION_LOG_STATUS_REPORT))

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

            for market_info in self._market_infos.values():
                self.c_process_market(market_info)
        finally:
            self._last_timestamp = timestamp

    cdef c_place_orders(self, object market_info):
        """
        Places an individual order specified by the user input if the user has enough balance and if the order quantity
        can be broken up to the number of desired orders

        :param market_info: a market trading pair
        """
        cdef:
            ExchangeBase market = market_info.market
            curr_order_amount = min(self._order_amount / self._num_individual_orders, self._quantity_remaining)
            object quantized_amount = market.c_quantize_order_amount(market_info.trading_pair, Decimal(curr_order_amount))
            object quantized_price = market.c_quantize_order_price(market_info.trading_pair, Decimal(self._order_price))

        self.logger().info(f"Checking to see if the incremental order size is possible")
        self.logger().info(f"Checking to see if the user has enough balance to place orders")

        if quantized_amount != 0:
            if self.c_has_enough_balance(market_info):
                order_id = self.c_buy_with_specific_market(market_info,
                                                            amount = quantized_amount)
                self.logger().info("Market buy order has been executed")
                self._quantity_remaining = Decimal(self._quantity_remaining) - quantized_amount

            else:
                self.logger().info(f"Not enough balance to run the strategy. Please check balances and try again.")
        else:
            self.logger().warning(f"Not possible to break the order into the desired number of segments.")

    cdef c_has_enough_balance(self, object market_info):
        """
        Checks to make sure the user has the sufficient balance in order to place the specified order

        :param market_info: a market trading pair
        :return: True if user has enough balance, False if not
        """
        cdef:
            ExchangeBase market = market_info.market
            double base_asset_balance = market.c_get_balance(market_info.base_asset)
            double quote_asset_balance = market.c_get_balance(market_info.quote_asset)
            OrderBook order_book = market_info.order_book
            double price = order_book.c_get_price_for_volume(True, float(self._quantity_remaining)).result_price

        return quote_asset_balance >= float(self._quantity_remaining) * price if self._is_buy else base_asset_balance >= float(self._quantity_remaining)

    cdef c_process_market(self, object market_info):
        """
        Checks if enough time has elapsed from previous order to place order and if so, calls c_place_orders() and
        cancels orders if they are older than self._cancel_order_wait_time.

        :param market_info: a market trading pair
        """
        cdef:
            ExchangeBase maker_market = market_info.market
            set cancel_order_ids = set()

        if self._quantity_remaining > 0:

            # If current timestamp is greater than the start timestamp and its the first order
            if (self._current_timestamp > self._previous_timestamp) and (self._first_order):

                self.logger().info(f"Trying to place orders now. ")
                self._previous_timestamp = self._current_timestamp
                self.c_place_orders(market_info)
                self._first_order = False

            # If current timestamp is greater than the (start timestamp + period(days)) place orders
            elif (self._current_timestamp > self._previous_timestamp + days2timestamp(self._days_period)) and (self._first_order is False):

                self.logger().info(f"Current time: "
                                   f"{datetime.fromtimestamp(self._current_timestamp).strftime('%Y-%m-%d %H:%M:%S')} "
                                   f"is now a period greater than "
                                   f"Previous time: "
                                   f"{datetime.fromtimestamp(self._previous_timestamp).strftime('%Y-%m-%d %H:%M:%S')} "
                                   f" with period: {self._days_period} days. Trying to place orders now. ")
                self.c_place_orders(market_info)
                self._previous_timestamp = self._current_timestamp

        active_orders = self.market_info_to_active_orders.get(market_info, [])
 
        # Not applicable for market order!
        # if len(active_orders) > 0:
        #     for active_order in active_orders:
        #         if self._current_timestamp >= self._time_to_cancel[active_order.client_order_id]:
        #             cancel_order_ids.add(active_order.client_order_id)

        # if len(cancel_order_ids) > 0:

        #     for order in cancel_order_ids:
        #         self.c_cancel_order(market_info, order)
