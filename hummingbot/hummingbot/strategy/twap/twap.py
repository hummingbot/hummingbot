import logging
import statistics
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from hummingbot.client.performance import PerformanceMetrics
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.event.events import MarketOrderFailureEvent, OrderCancelledEvent, OrderExpiredEvent
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.conditional_execution_state import ConditionalExecutionState, RunAlwaysExecutionState
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase

twap_logger = None


class TwapTradeStrategy(StrategyPyBase):
    """
    Time-Weighted Average Price strategy
    This strategy is intended for  executing trades evenly over a specified time period.
    """

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global twap_logger
        if twap_logger is None:
            twap_logger = logging.getLogger(__name__)
        return twap_logger

    def __init__(self,
                 market_infos: List[MarketTradingPairTuple],
                 is_buy: bool,
                 target_asset_amount: Decimal,
                 order_step_size: Decimal,
                 order_price: Decimal,
                 order_delay_time: float = 10.0,
                 execution_state: ConditionalExecutionState = None,
                 cancel_order_wait_time: Optional[float] = 60.0,
                 status_report_interval: float = 900):
        """
        :param market_infos: list of market trading pairs
        :param is_buy: if the order is to buy
        :param target_asset_amount: qty of the order to place
        :param order_step_size: amount of base asset to be configured in each order
        :param order_price: price to place the order at
        :param order_delay_time: how long to wait between placing trades
        :param execution_state: execution state object with the conditions that should be satisfied to run each tick
        :param cancel_order_wait_time: how long to wait before canceling an order
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
        self._order_delay_time = order_delay_time
        self._quantity_remaining = target_asset_amount
        self._time_to_cancel = {}
        self._is_buy = is_buy
        self._target_asset_amount = target_asset_amount
        self._order_step_size = order_step_size
        self._first_order = True
        self._previous_timestamp = 0
        self._last_timestamp = 0
        self._order_price = order_price
        self._execution_state = execution_state or RunAlwaysExecutionState()

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

    @property
    def place_orders(self):
        return self._place_orders

    def configuration_status_lines(self,):
        lines = ["", "  Configuration:"]

        for market_info in self._market_infos.values():
            lines.append("    "
                         f"Total amount: {PerformanceMetrics.smart_round(self._target_asset_amount)} "
                         f"{market_info.base_asset}    "
                         f"Order price: {PerformanceMetrics.smart_round(self._order_price)} "
                         f"{market_info.quote_asset}    "
                         f"Order size: {PerformanceMetrics.smart_round(self._order_step_size)} "
                         f"{market_info.base_asset}")

        lines.append(f"    Execution type: {self._execution_state}")

        return lines

    def filled_trades(self):
        """
        Returns a list of all filled trades generated from limit orders with the same trade type the strategy
        has in its configuration
        """
        trade_type = TradeType.BUY if self._is_buy else TradeType.SELL
        return [trade
                for trade
                in self.trades
                if trade.trade_type == trade_type.name and trade.order_type == OrderType.LIMIT]

    def format_status(self) -> str:
        lines: list = []
        warning_lines: list = []

        lines.extend(self.configuration_status_lines())

        for market_info in self._market_infos.values():

            active_orders = self.market_info_to_active_orders.get(market_info, [])

            warning_lines.extend(self.network_warning([market_info]))

            markets_df = self.market_status_data_frame([market_info])
            lines.extend(["", "  Markets:"] + ["    " + line for line in markets_df.to_string().split("\n")])

            assets_df = self.wallet_balance_data_frame([market_info])
            lines.extend(["", "  Assets:"] + ["    " + line for line in assets_df.to_string().split("\n")])

            # See if there're any open orders.
            if len(active_orders) > 0:
                price_provider = None
                for market_info in self._market_infos.values():
                    price_provider = market_info
                if price_provider is not None:
                    df = LimitOrder.to_pandas(active_orders, mid_price=float(price_provider.get_mid_price()))
                    if self._is_buy:
                        # Descend from the price closest to the mid price
                        df = df.sort_values(by=['Price'], ascending=False)
                    else:
                        # Ascend from the price closest to the mid price
                        df = df.sort_values(by=['Price'], ascending=True)
                    df = df.reset_index(drop=True)
                    df_lines = df.to_string().split("\n")
                    lines.extend(["", "  Active orders:"] +
                                 ["    " + line for line in df_lines])
            else:
                lines.extend(["", "  No active maker orders."])

            filled_trades = self.filled_trades()
            average_price = (statistics.mean([trade.price for trade in filled_trades])
                             if filled_trades
                             else Decimal(0))
            lines.extend(["",
                          f"  Average filled orders price: "
                          f"{PerformanceMetrics.smart_round(average_price)} "
                          f"{market_info.quote_asset}"])

            lines.extend([f"  Pending amount: {PerformanceMetrics.smart_round(self._quantity_remaining)} "
                          f"{market_info.base_asset}"])

            warning_lines.extend(self.balance_warning([market_info]))

        if warning_lines:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    def did_fill_order(self, order_filled_event):
        """
        Output log for filled order.
        :param order_filled_event: Order filled event
        """
        order_id: str = order_filled_event.order_id
        market_info = self.order_tracker.get_shadow_market_pair_from_order_id(order_id)

        if market_info is not None:
            self.log_with_clock(logging.INFO,
                                f"({market_info.trading_pair}) Limit {order_filled_event.trade_type.name.lower()} order of "
                                f"{order_filled_event.amount} {market_info.base_asset} filled.")

    def did_complete_buy_order(self, order_completed_event):
        """
        Output log for completed buy order.
        :param order_completed_event: Order completed event
        """
        self.log_complete_order(order_completed_event)

    def did_complete_sell_order(self, order_completed_event):
        """
        Output log for completed sell order.
        :param order_completed_event: Order completed event
        """
        self.log_complete_order(order_completed_event)

    def log_complete_order(self, order_completed_event):
        """
        Output log for completed order.
        :param order_completed_event: Order completed event
        """
        order_id: str = order_completed_event.order_id
        market_info = self.order_tracker.get_market_pair_from_order_id(order_id)

        if market_info is not None:
            limit_order_record = self.order_tracker.get_limit_order(market_info, order_id)
            order_type = "buy" if limit_order_record.is_buy else "sell"
            self.log_with_clock(
                logging.INFO,
                f"({market_info.trading_pair}) Limit {order_type} order {order_id} "
                f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                f"{limit_order_record.price} {limit_order_record.quote_currency}) has been filled."
            )

    def did_cancel_order(self, cancelled_event: OrderCancelledEvent):
        self.update_remaining_after_removing_order(cancelled_event.order_id, 'cancel')

    def did_fail_order(self, order_failed_event: MarketOrderFailureEvent):
        self.update_remaining_after_removing_order(order_failed_event.order_id, 'fail')

    def did_expire_order(self, expired_event: OrderExpiredEvent):
        self.update_remaining_after_removing_order(expired_event.order_id, 'expire')

    def update_remaining_after_removing_order(self, order_id: str, event_type: str):
        market_info = self.order_tracker.get_market_pair_from_order_id(order_id)

        if market_info is not None:
            limit_order_record = self.order_tracker.get_limit_order(market_info, order_id)
            if limit_order_record is not None:
                self.log_with_clock(logging.INFO, f"Updating status after order {event_type} (id: {order_id})")
                self._quantity_remaining += limit_order_record.quantity

    def process_market(self, market_info):
        """
        Checks if enough time has elapsed from previous order to place order and if so, calls place_orders_for_market() and
        cancels orders if they are older than self._cancel_order_wait_time.

        :param market_info: a market trading pair
        """
        if self._quantity_remaining > 0:

            # If current timestamp is greater than the start timestamp and its the first order
            if (self.current_timestamp > self._previous_timestamp) and self._first_order:

                self.logger().info("Trying to place orders now. ")
                self._previous_timestamp = self.current_timestamp
                self.place_orders_for_market(market_info)
                self._first_order = False

            # If current timestamp is greater than the start timestamp + time delay place orders
            elif (self.current_timestamp > self._previous_timestamp + self._order_delay_time) and (self._first_order is False):
                self.logger().info("Current time: "
                                   f"{datetime.fromtimestamp(self.current_timestamp).strftime('%Y-%m-%d %H:%M:%S')} "
                                   "is now greater than "
                                   "Previous time: "
                                   f"{datetime.fromtimestamp(self._previous_timestamp).strftime('%Y-%m-%d %H:%M:%S')} "
                                   f" with time delay: {self._order_delay_time}. Trying to place orders now. ")
                self._previous_timestamp = self.current_timestamp
                self.place_orders_for_market(market_info)

        active_orders = self.market_info_to_active_orders.get(market_info, [])

        orders_to_cancel = (active_order
                            for active_order
                            in active_orders
                            if self.current_timestamp >= self._time_to_cancel[active_order.client_order_id])

        for order in orders_to_cancel:
            self.cancel_order(market_info, order.client_order_id)

    def start(self, clock: Clock, timestamp: float):
        self.logger().info(f"Waiting for {self._order_delay_time} to place orders")
        self._previous_timestamp = timestamp
        self._last_timestamp = timestamp

    def tick(self, timestamp: float):
        """
        Clock tick entry point.
        For the TWAP strategy, this function simply checks for the readiness and connection status of markets, and
        then delegates the processing of each market info to process_market().

        :param timestamp: current tick timestamp
        """

        try:
            self._execution_state.process_tick(timestamp, self)
        finally:
            self._last_timestamp = timestamp

    def process_tick(self, timestamp: float):
        """
        Clock tick entry point.
        For the TWAP strategy, this function simply checks for the readiness and connection status of markets, and
        then delegates the processing of each market info to process_market().
        """
        current_tick = timestamp // self._status_report_interval
        last_tick = (self._last_timestamp // self._status_report_interval)
        should_report_warnings = current_tick > last_tick

        if not self._all_markets_ready:
            self._all_markets_ready = all([market.ready for market in self.active_markets])
            if not self._all_markets_ready:
                # Markets not ready yet. Don't do anything.
                if should_report_warnings:
                    self.logger().warning("Markets are not ready. No market making trades are permitted.")
                return

        if (should_report_warnings
                and not all([market.network_status is NetworkStatus.CONNECTED for market in self.active_markets])):
            self.logger().warning("WARNING: Some markets are not connected or are down at the moment. Market "
                                  "making may be dangerous when markets or networks are unstable.")

        for market_info in self._market_infos.values():
            self.process_market(market_info)

    def cancel_active_orders(self):
        # Nothing to do here
        pass

    def place_orders_for_market(self, market_info):
        """
        Places an individual order specified by the user input if the user has enough balance and if the order quantity
        can be broken up to the number of desired orders
        :param market_info: a market trading pair
        """
        market: ExchangeBase = market_info.market
        curr_order_amount = min(self._order_step_size, self._quantity_remaining)
        quantized_amount = market.quantize_order_amount(market_info.trading_pair, Decimal(curr_order_amount))
        quantized_price = market.quantize_order_price(market_info.trading_pair, Decimal(self._order_price))

        self.logger().debug("Checking to see if the incremental order size is possible")
        self.logger().debug("Checking to see if the user has enough balance to place orders")

        if quantized_amount != 0:
            if self.has_enough_balance(market_info, quantized_amount):
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

            else:
                self.logger().info("Not enough balance to run the strategy. Please check balances and try again.")
        else:
            self.logger().warning("Not possible to break the order into the desired number of segments.")

    def has_enough_balance(self, market_info, amount: Decimal):
        """
        Checks to make sure the user has the sufficient balance in order to place the specified order

        :param market_info: a market trading pair
        :param amount: order amount
        :return: True if user has enough balance, False if not
        """
        market: ExchangeBase = market_info.market
        base_asset_balance = market.get_balance(market_info.base_asset)
        quote_asset_balance = market.get_balance(market_info.quote_asset)
        order_book: OrderBook = market_info.order_book
        price = order_book.get_price_for_volume(True, float(amount)).result_price

        return quote_asset_balance >= (amount * Decimal(price)) \
            if self._is_buy \
            else base_asset_balance >= amount
