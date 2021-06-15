from datetime import datetime
from decimal import Decimal
import logging
from typing import (
    List,
    Tuple,
    Optional,
    Dict
)

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.event.events import OrderType
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase

d5vwap_logger = None


class Dev5TwapTradeStrategy(StrategyPyBase):

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global d5vwap_logger
        if d5vwap_logger is None:
            d5vwap_logger = logging.getLogger(__name__)
        return d5vwap_logger

    def __init__(self,
                 market_infos: List[MarketTradingPairTuple],
                 order_type: str = "limit",
                 order_price: Optional[float] = None,
                 cancel_order_wait_time: Optional[float] = 60.0,
                 is_buy: bool = True,
                 time_delay: float = 10.0,
                 is_vwap=True,
                 num_individual_orders: int = 1,
                 percent_slippage: float = 0,
                 order_percent_of_volume: float = 100,
                 order_amount: Decimal = Decimal("1.0"),
                 status_report_interval: float = 900):
        """
        :param market_infos: list of market trading pairs
        :param order_type: type of order to place
        :param order_price: price to place the order at
        :param cancel_order_wait_time: how long to wait before cancelling an order
        :param is_buy: if the order is to buy
        :param time_delay: how long to wait between placing trades
        :param num_individual_orders: how many individual orders to split the order into
        :param order_amount: qty of the order to place
        :param status_report_interval: how often to report network connection related warnings, if any
        """

        if len(market_infos) < 1:
            raise ValueError("market_infos must not be empty.")

        super().__init__()
        self._market_infos = {
            (market_info.market, market_info.trading_pair): market_info
            for market_info in market_infos
        }
        self._all_markets_ready = False
        self._place_orders = True
        self._status_report_interval = status_report_interval
        self._time_delay = time_delay
        self._num_individual_orders = num_individual_orders
        self._quantity_remaining = order_amount
        self._time_to_cancel = {}
        self._order_type = order_type
        self._is_buy = is_buy
        self._order_amount = order_amount
        self._first_order = True
        self._is_vwap = is_vwap
        self._percent_slippage = Decimal(percent_slippage)
        self._order_percent_of_volume = order_percent_of_volume
        self._has_outstanding_order = False
        self._previous_timestamp = 0
        self._last_timestamp = 0
        self._order_price = Decimal("NaN")

        if order_price is not None:
            self._order_price = Decimal(order_price)
        if cancel_order_wait_time is not None:
            self._cancel_order_wait_time = cancel_order_wait_time

        all_markets = set([market_info.market for market_info in market_infos])

        self.add_markets(list(all_markets))

    @property
    def active_bids(self) -> List[Tuple[ExchangeBase, LimitOrder]]:
        return self.order_tracker.active_bids

    @property
    def active_asks(self) -> List[Tuple[ExchangeBase, LimitOrder]]:
        return self.order_tracker.active_asks

    @property
    def active_limit_orders(self) -> List[Tuple[ExchangeBase, LimitOrder]]:
        return self.order_tracker.active_limit_orders

    @property
    def in_flight_cancels(self) -> Dict[str, float]:
        return self.order_tracker.in_flight_cancels

    @property
    def market_info_to_active_orders(self) -> Dict[MarketTradingPairTuple, List[LimitOrder]]:
        return self.order_tracker.market_pair_to_active_orders

    def format_status(self) -> str:
        lines = []
        warning_lines = []

        for market_info in self._market_infos.values():
            active_orders = self.market_info_to_active_orders.get(market_info, [])

            warning_lines.extend(self.network_warning([market_info]))

            markets_df = self.market_status_data_frame([market_info])
            lines.extend(["", "  Markets:"] + ["    " + line for line in str(markets_df).split("\n")])

            assets_df = self.wallet_balance_data_frame([market_info])
            lines.extend(["", "  Assets:"] + ["    " + line for line in str(assets_df).split("\n")])

            # See if there're any open orders.
            if active_orders:
                df = LimitOrder.to_pandas(active_orders)
                df_lines = str(df).split("\n")
                lines.extend(["", "  Active orders:"] +
                             ["    " + line for line in df_lines])
            else:
                lines.extend(["", "  No active maker orders."])

            warning_lines.extend(self.balance_warning([market_info]))

        if warning_lines:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    def did_fill_order(self, order_filled_event):
        """
        Output log for filled order.

        :param order_filled_event: Order filled event
        """

        filled_order_id: str = order_filled_event.order_id
        market_trading_pair = self.order_tracker.get_shadow_market_pair_from_order_id(filled_order_id)

        if market_trading_pair is not None:
            self.log_with_clock(
                logging.INFO,
                f"({market_trading_pair.trading_pair}) Limit {order_filled_event.trade_type.name.lower()} order of "
                f"{order_filled_event.amount} {market_trading_pair.base_asset} filled.")

    def did_complete_buy_order(self, order_completed_event):
        """
        Output log for completed buy order.

        :param order_completed_event: Order completed event
        """

        self.log_complete_order(order_completed_event)
        self.check_last_order(order_completed_event)

    def did_complete_sell_order(self, order_completed_event):
        """
        Output log for completed sell order.

        :param order_completed_event: Order completed event
        """

        self.log_complete_order(order_completed_event)
        self.check_last_order(order_completed_event)

    def log_complete_order(self, order_completed_event):
        """
        Output log for completed order.
        :param order_completed_event: Order completed event
        """
        order_id: str = order_completed_event.order_id
        market_info = self.order_tracker.get_market_pair_from_order_id(order_id)

        if market_info is not None:
            limit_order_record = self.order_tracker.get_limit_order(market_info, order_id)
            # If its not market order
            if limit_order_record is not None:
                order_type = "buy" if limit_order_record.is_buy else "sell"
                self.log_with_clock(
                    logging.INFO,
                    f"({market_info.trading_pair}) Limit {order_type} order {order_id} "
                    f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                    f"{limit_order_record.price} {limit_order_record.quote_currency}) has been filled."
                )
            else:
                market_order_record = self.order_tracker.get_market_order(market_info, order_id)
                order_type = "buy" if market_order_record.is_buy else "sell"
                self.log_with_clock(
                    logging.INFO,
                    f"({market_info.trading_pair}) Market {order_type} order {order_id} "
                    f"({market_order_record.amount} {market_order_record.base_asset}) has been filled."
                )

    def did_fail_order(self, order_failed_event):
        if self._is_vwap:
            self.check_last_order(order_failed_event)

    def did_cancel_order(self, cancelled_event):
        if self._is_vwap:
            self.check_last_order(cancelled_event)

    def did_expire_order(self, expired_event):
        if self._is_vwap:
            self.check_last_order(expired_event)

    def start(self, clock: Clock, timestamp: float):
        self.logger().info(f"Waiting for {self._time_delay} to place orders")
        self._previous_timestamp = timestamp
        self._last_timestamp = timestamp

    def tick(self, timestamp: float):
        """
        Clock tick entry point.

        For this strategy, this function simply checks for the readiness and connection status of markets, and
        then delegates the processing of each market info to process_market().

        :param timestamp: current tick timestamp
        """
        current_tick = (timestamp // self._status_report_interval)
        last_tick = (self._last_timestamp // self._status_report_interval)
        should_report_warnings = current_tick > last_tick

        try:
            if not self._all_markets_ready:
                self._all_markets_ready = all([market.ready for market in self.active_markets])
                if not self._all_markets_ready:
                    # Markets not ready yet. Don't do anything.
                    if should_report_warnings:
                        self.logger().warning("Markets are not ready. No market making trades are permitted.")
                    return

            if should_report_warnings and not all([market.network_status is NetworkStatus.CONNECTED
                                                   for market in self._sb_markets]):
                self.logger().warning("WARNING: Some markets are not connected or are down at the moment. Market "
                                      "making may be dangerous when markets or networks are unstable.")

            for market_info in self._market_infos.values():
                self.process_market(market_info)
        finally:
            self._last_timestamp = timestamp

    def check_last_order(self, order_event):
        """
        Check to see if the event is called on an order made by this strategy. If it is made from this strategy,
        set self._has_outstanding_order to False to unblock further VWAP processes.
        """
        market_info = self.order_tracker.get_market_pair_from_order_id(order_event.order_id)
        if market_info is not None:
            self._has_outstanding_order = False

    def place_orders(self, market_info):
        """
        If TWAP, places an individual order specified by the user input if the user has enough balance and if the order quantity
        can be broken up to the number of desired orders
        Else, places an individual order capped at order_percent_of_volume * open order volume up to percent_slippage

        :param market_info: a market trading pair
        """

        market: ExchangeBase = market_info.market
        curr_order_amount = min(self._order_amount / self._num_individual_orders, self._quantity_remaining)
        quantized_amount = market.quantize_order_amount(market_info.trading_pair, Decimal(curr_order_amount))
        quantized_price = market.quantize_order_price(market_info.trading_pair, Decimal(self._order_price))
        order_book: OrderBook = market_info.order_book

        if self._is_vwap:
            order_price = order_book.get_price(self._is_buy) if self._order_type == "market" else self._order_price
            order_price = Decimal(order_price)
            slippage_amount = order_price * Decimal(self._percent_slippage) * Decimal("0.01")
            if self._is_buy:
                slippage_price = order_price + slippage_amount
            else:
                slippage_price = order_price - slippage_amount

            total_order_volume = order_book.get_volume_for_price(self._is_buy, float(slippage_price))
            order_cap = self._order_percent_of_volume * total_order_volume.result_volume * 0.01

            quantized_amount = quantized_amount.min(Decimal.from_float(order_cap))

        self.logger().info("Checking to see if the user has enough balance to place orders")

        if quantized_amount != 0:
            if self.has_enough_balance(market_info):

                if self._order_type == "market":
                    if self._is_buy:
                        order_id = self.buy_with_specific_market(market_info,
                                                                 amount=quantized_amount)
                        self.logger().info("Market buy order has been executed")
                    else:
                        order_id = self.sell_with_specific_market(market_info,
                                                                  amount=quantized_amount)
                        self.logger().info("Market sell order has been executed")
                else:
                    if self._is_buy:
                        order_id = self.buy_with_specific_market(market_info,
                                                                 amount=quantized_amount,
                                                                 order_type=OrderType.LIMIT,
                                                                 price=quantized_price)
                        self.logger().info("Limit buy order has been placed")

                    else:
                        order_id = self.sell_with_specific_market(market_info,
                                                                  amount=quantized_amount,
                                                                  order_type=OrderType.LIMIT,
                                                                  price=quantized_price)
                        self.logger().info("Limit sell order has been placed")
                    self._time_to_cancel[order_id] = self.current_timestamp + self._cancel_order_wait_time

                self._quantity_remaining = Decimal(self._quantity_remaining) - quantized_amount
                self._has_outstanding_order = True

            else:
                self.logger().info("Not enough balance to run the strategy. Please check balances and try again.")
        else:
            self.logger().warning("Not possible to break the order into the desired number of segments.")

    def has_enough_balance(self, market_info) -> bool:
        """
        Checks to make sure the user has the sufficient balance in order to place the specified order

        :param market_info: a market trading pair
        :return: True if user has enough balance, False if not
        """
        market: ExchangeBase = market_info.market
        base_asset_balance = market.get_balance(market_info.base_asset)
        quote_asset_balance = market.get_balance(market_info.quote_asset)
        price = market_info.order_book.get_price_for_volume(True,
                                                            float(self._quantity_remaining)).result_price

        return (quote_asset_balance >= float(self._quantity_remaining) * price
                if self._is_buy
                else base_asset_balance >= float(self._quantity_remaining))

    def process_market(self, market_info):
        """
        If the user selected TWAP, checks if enough time has elapsed from previous order to place order and if so, calls place_orders() and
        cancels orders if they are older than self._cancel_order_wait_time.
        Otherwise, if there is not an outstanding order, calls place_orders().

        :param market_info: a market trading pair
        """
        cancel_order_ids = set()

        if not self._is_vwap:  # TWAP
            if self._quantity_remaining > 0:
                # If current timestamp is greater than the start timestamp and its the first order
                if self.current_timestamp > self._previous_timestamp and self._first_order:
                    self.logger().info("Trying to place orders now. ")
                    self._previous_timestamp = self.current_timestamp
                    self.place_orders(market_info)
                    self._first_order = False

                # If current timestamp is greater than the start timestamp + time delay place orders
                elif self.current_timestamp > self._previous_timestamp + self._time_delay and self._first_order is False:
                    self.logger().info("Current time: "
                                       f"{datetime.fromtimestamp(self.current_timestamp).strftime('%Y-%m-%d %H:%M:%S')} "
                                       "is now greater than "
                                       "Previous time: "
                                       f"{datetime.fromtimestamp(self._previous_timestamp).strftime('%Y-%m-%d %H:%M:%S')} "
                                       f" with time delay: {self._time_delay}. Trying to place orders now. ")
                    self._previous_timestamp = self.current_timestamp
                    self.place_orders(market_info)
        else:  # VWAP
            if not self._has_outstanding_order:
                self.place_orders(market_info)

        active_orders = self.market_info_to_active_orders.get(market_info, [])

        for active_order in active_orders:
            if self.current_timestamp >= self._time_to_cancel[active_order.client_order_id]:
                cancel_order_ids.add(active_order.client_order_id)

        for order in cancel_order_ids:
            self.cancel_order(market_info, order)
