# distutils: language=c++
import logging
from collections import namedtuple
from decimal import Decimal
from enum import Enum
import pandas as pd
from typing import List, Tuple
import time

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.event.events import (
    TradeType,
    OrderType,
)
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.market_order import MarketOrder
from hummingbot.strategy.strategy_base import StrategyBase
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.triangular_arbitrage.model.arbitrage cimport TradeDirection
from hummingbot.strategy.triangular_arbitrage.triangular_arbitrage_calculation cimport TriangularArbitrageCalculator
from hummingbot.strategy.triangular_arbitrage.order_tracking.arbitrage_execution_tracker import ArbitrageExecutionTracker

NaN = float("nan")
s_decimal_0 = Decimal(0)
as_logger = None

# this is an expedient for testing
Proposal = namedtuple("Proposal", "trading_pair amount is_buy")

cdef class TriangularArbitrageStrategy(StrategyBase):
    OPTION_LOG_STATUS_REPORT = 1 << 0
    OPTION_LOG_CREATE_ORDER = 1 << 1
    OPTION_LOG_ORDER_COMPLETED = 1 << 2
    OPTION_LOG_PROFITABILITY_STEP = 1 << 3
    OPTION_LOG_FULL_PROFITABILITY_STEP = 1 << 4
    OPTION_LOG_INSUFFICIENT_ASSET = 1 << 5
    OPTION_LOG_ALL = 0xfffffffffffffff

    @classmethod
    def logger(cls):
        global as_logger
        if as_logger is None:
            as_logger = logging.getLogger(__name__)
        return as_logger

    def __init__(self,
                 market_pairs: List[MarketTradingPairTuple],
                 min_profitability: Decimal,
                 triangular_arbitrage_calculator: TriangularArbitrageCalculator,
                 logging_options: int = OPTION_LOG_ORDER_COMPLETED,
                 use_oracle_conversion_rate: bool = False,
                 status_report_interval: Decimal = 60.0,
                 next_trade_delay_interval: float = 15.0,
                 failure_cool_down_interval: float = 60.0):

        super().__init__()

        self._all_markets_ready = False
        self._market_pairs = market_pairs
        self.c_add_markets([pair.market for pair in market_pairs])
        self._status_report_interval = status_report_interval
        self._last_timestamp = 0
        self._logging_options = logging_options
        self._triangular_arbitrage_module = triangular_arbitrage_calculator
        self._market_pairs = market_pairs

        self._arbitrage_execution_tracker = ArbitrageExecutionTracker(
            market_pairs[0].trading_pair,
            market_pairs[1].trading_pair,
            market_pairs[2].trading_pair,
            next_trade_delay_interval,
        )
        self._trading_pair_to_market_pair_tuple = {}
        for pair in market_pairs:
            self._trading_pair_to_market_pair_tuple[pair.trading_pair] = pair

        self._failed_market_order_count = 0
        self._failed_order_tolerance = 100
        self._recent_failure = False
        self._last_failure_timestamp = 0
        self._failure_delay_interval = failure_cool_down_interval

        self._arbitrage_opportunity = None

    @property
    def tracked_limit_orders(self) -> List[Tuple[ExchangeBase, LimitOrder]]:
        return self._sb_order_tracker.tracked_limit_orders

    @property
    def tracked_market_orders(self) -> List[Tuple[ExchangeBase, MarketOrder]]:
        return self._sb_order_tracker.tracked_market_orders

    @property
    def tracked_limit_orders_data_frame(self) -> List[pd.DataFrame]:
        return self._sb_order_tracker.tracked_limit_orders_data_frame

    @property
    def tracked_market_orders_data_frame(self) -> List[pd.DataFrame]:
        return self._sb_order_tracker.tracked_market_orders_data_frame

    @property
    def triangular_arbitrage_module(self):
        return self._triangular_arbitrage_module

    cdef c_tick(self, double timestamp):
        """
        Clock tick entry point.

        For the triangular arbitrage strategy, this function checks for the readiness and
        connection status of markets, and then checks the arbitrage calculator status. If there
        is an arbitrage opportunity, it passes control to the order execution module.

        :param timestamp: current tick timestamp
        """
        StrategyBase.c_tick(self, timestamp)

        cdef:
            int64_t current_tick = <int64_t>(timestamp // self._status_report_interval)
            int64_t last_tick = <int64_t>(self._last_timestamp // self._status_report_interval)
            bint should_report_warnings = ((current_tick > last_tick) and
                                           (self._logging_options & self.OPTION_LOG_STATUS_REPORT))
        try:
            if not self._all_markets_ready:
                self._all_markets_ready = all([market.ready for market in self._sb_markets])
                if not self._all_markets_ready:
                    # Markets not ready yet. Don't do anything.
                    if should_report_warnings:
                        self.logger().warning(f"Markets are not ready. No trading is permitted.")
                    return
                else:
                    if self.OPTION_LOG_STATUS_REPORT:
                        self.logger().info(f"Markets are ready. Trading started.")

            if not all([market.network_status is NetworkStatus.CONNECTED for market in self._sb_markets]):
                if should_report_warnings:
                    self.logger().warning(f"Markets are not all online.")
                    # stop execution?

            if self._recent_failure:
                if (time.time() > self._last_failure_timestamp + self._failure_delay_interval):
                    self._recent_failure = False
                else:
                    return

            if self._arbitrage_execution_tracker.ready:
                arbitrage_opportunity = self._triangular_arbitrage_module.update_opportunity(self._market_pairs)

                if arbitrage_opportunity is not None:
                    self._arbitrage_opportunity = arbitrage_opportunity
                    if arbitrage_opportunity[0].can_execute:
                        self._arbitrage_execution_tracker.set_not_ready()
                        self.c_execute_opportunity(arbitrage_opportunity[0])
            elif not self._arbitrage_execution_tracker.recovering:
                self.continue_execution()

        finally:
            self._last_timestamp = timestamp

    def sufficient_funds(self, order):
        if order.is_all_in:
            return True
        trading_pair_tuple = self._trading_pair_to_market_pair_tuple[order.trading_pair]
        market = trading_pair_tuple.market
        if order.trade_type == TradeType.BUY:
            price = Decimal('1.1') * market.get_price(order.trading_pair, True)
            total = price * order.amount_remaining

            return (market.get_available_balance(trading_pair_tuple.quote_asset) > total)
        else:
            return (market.get_available_balance(trading_pair_tuple.base_asset) > order.amount_remaining)

    cdef c_execute_opportunity(self, arbitrage_opportunity):
        order_1, order_2, order_3, *others = arbitrage_opportunity.orders

        trading_pair_1 = order_1.trading_pair
        trading_pair_2 = order_2.trading_pair
        trading_pair_3 = order_3.trading_pair

        trading_pair_tuple_1 = self._trading_pair_to_market_pair_tuple[trading_pair_1]
        trading_pair_tuple_2 = self._trading_pair_to_market_pair_tuple[trading_pair_2]
        trading_pair_tuple_3 = self._trading_pair_to_market_pair_tuple[trading_pair_3]

        market_1: ExchangeBase = trading_pair_tuple_1.market
        market_2: ExchangeBase = trading_pair_tuple_2.market
        market_3: ExchangeBase = trading_pair_tuple_3.market

        quant_amount_1 = market_1.c_quantize_order_amount(trading_pair_1, order_1.amount)
        quant_amount_2 = market_2.c_quantize_order_amount(trading_pair_2, order_2.amount)
        quant_amount_3 = market_3.c_quantize_order_amount(trading_pair_3, order_3.amount)

        if not all([quant_amount_1 > 0, quant_amount_2 > 0, quant_amount_3 > 0]):
            self._arbitrage_execution_tracker.reset(True)
            self._arbitrage_execution_tracker.set_ready()
            return
        else:
            o1, o2, o3 = self._arbitrage_execution_tracker.add_opportunity(arbitrage_opportunity.orders)

            if self.sufficient_funds(o1):
                self._place_order(o1)
            if self.sufficient_funds(o2):
                self._place_order(o2)
            if self.sufficient_funds(o3):
                self._place_order(o3)

    def continue_execution(self):
        if self._arbitrage_execution_tracker.finished:
            if self._arbitrage_execution_tracker.reverse:
                # the following will only execute if an order
                # failure has occurred
                self._recent_failure = True
                self._last_failure_timestamp = time.time()
                self.logger().warning(f"An order failure has occurred. Trading will cease for "
                                      f"{int(self._failure_delay_interval)} seconds")
            else:
                if not self._arbitrage_execution_tracker.ready:
                    self.logger().info(f"Cooling off from previous trade. Resuming in "
                                       f"{int(self._arbitrage_execution_tracker.trade_delay)} seconds")
            if not self._arbitrage_execution_tracker.ready:
                self._arbitrage_execution_tracker.reset()
        else:
            for action in self._arbitrage_execution_tracker.get_next_actions():
                if action.action == "place":
                    if self.sufficient_funds(action.order):
                        self._place_order(action.order)
                    else:
                        if self._arbitrage_execution_tracker.reverse:
                            trading_pair_tuple = self._trading_pair_to_market_pair_tuple[action.order.trading_pair]
                            market = trading_pair_tuple.market
                            if action.order.trade_type == TradeType.BUY:
                                wallet_balance = market.get_available_balance(trading_pair_tuple.quote_asset)
                            else:
                                wallet_balance = market.get_available_balance(trading_pair_tuple.base_asset)
                            all_in_order = self._arbitrage_execution_tracker.all_in_order(action.order, wallet_balance)
                            self._place_order(all_in_order)
                elif action.action == "cancel":
                    trading_pair_tuple = self._trading_pair_to_market_pair_tuple[action.order.trading_pair]
                    self.c_cancel_order(trading_pair_tuple, action.order.id)
                elif action.action == "place_all_in":
                    trading_pair_tuple = self._trading_pair_to_market_pair_tuple[action.order.trading_pair]
                    market = trading_pair_tuple.market
                    if action.order.trade_type == TradeType.BUY:
                        wallet_balance = market.get_available_balance(trading_pair_tuple.quote_asset)
                    else:
                        wallet_balance = market.get_available_balance(trading_pair_tuple.base_asset)
                    all_in_order = self._arbitrage_execution_tracker.all_in_order(action.order, wallet_balance)
                    self._place_order(all_in_order)

    def _place_order(self, order) -> bool:
        market_trading_pair = self._trading_pair_to_market_pair_tuple[order.trading_pair]
        market = market_trading_pair.market

        place_order_fn = self.buy_with_specific_market if order.trade_type == TradeType.BUY else self.sell_with_specific_market

        try:
            if order.price is not None:
                order_id = place_order_fn(market_trading_pair, order.amount, OrderType.LIMIT, order.price)
            else:
                order_id = place_order_fn(market_trading_pair, order.amount, OrderType.MARKET)
            self._arbitrage_execution_tracker.update_order_id(order.trading_pair, order_id)
            return True
        except Exception as e:
            print(e)
            return False

    def format_status(self):
        cdef:
            list lines = []
            list warning_lines = []

        warning_lines.extend(self.network_warning(self._market_pairs))
        markets_df = self.market_status_data_frame(self._market_pairs)
        lines.extend(["", "  Markets:"] +
                     ["    " + line for line in str(markets_df).split("\n")])

        assets_df = self.wallet_balance_data_frame(self._market_pairs)
        lines.extend(["", "  Assets:"] +
                     ["    " + line for line in str(assets_df).split("\n")])

        lines.extend(["", "  Latest Arbitrage Opportunity Status:"])
        if self._arbitrage_opportunity is not None:
            try:
                for opportunity in self._arbitrage_opportunity:
                    if opportunity.direction == TradeDirection.Clockwise:
                        lines.extend(["", "   CLOCKWISE:"])
                        lines.extend(["", "".join(f"     {order}\n" for order in opportunity.orders)])
                    else:
                        lines.extend(["", "   COUNTER-CLOCKWIZE:"])
                        lines.extend(["", "".join(f"     {order}\n" for order in opportunity.orders)])
            except Exception as e:
                print(e)

        tracked_limit_orders = self.tracked_limit_orders
        tracked_market_orders = self.tracked_market_orders

        if len(tracked_limit_orders) > 0 or len(tracked_market_orders) > 0:
            tracked_limit_orders_df = self.tracked_limit_orders_data_frame
            tracked_market_orders_df = self.tracked_market_orders_data_frame
            df_limit_lines = (str(tracked_limit_orders_df).split("\n")
                              if len(tracked_limit_orders) > 0
                              else list())
            df_market_lines = (str(tracked_market_orders_df).split("\n")
                               if len(tracked_market_orders) > 0
                               else list())
            lines.extend(["", "  Pending limit orders:"] +
                         ["    " + line for line in df_limit_lines] +
                         ["    " + line for line in df_market_lines])
        else:
            lines.extend(["", "  No pending limit orders."])

        warning_lines.extend(self.balance_warning(self._market_pairs))

        if len(warning_lines) > 0:
            lines.extend(["", "  *** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    cdef _did_create_order(self, object order_created_event):
        cdef:
            str order_id = order_created_event.order_id
            object market_trading_pair_tuple = self._sb_order_tracker.c_get_market_pair_from_order_id(order_id)
        if market_trading_pair_tuple is not None:
            trading_pair = market_trading_pair_tuple.trading_pair
            self._arbitrage_execution_tracker.order_placed(trading_pair)

    cdef c_did_create_buy_order(self, object buy_order_created_event):
        self._did_create_order(buy_order_created_event)

    cdef c_did_create_sell_order(self, object sell_order_created_event):
        self._did_create_order(sell_order_created_event)

    cdef _did_complete_order(self, object completed_event):
        cdef:
            str order_id = completed_event.order_id
            object market_trading_pair_tuple = self._sb_order_tracker.c_get_market_pair_from_order_id(order_id)
        if market_trading_pair_tuple is not None:
            trading_pair = market_trading_pair_tuple.trading_pair
            self._arbitrage_execution_tracker.order_complete(order_id, trading_pair)

    cdef c_did_complete_buy_order(self, object buy_order_completed_event):
        self._did_complete_order(buy_order_completed_event)

    cdef c_did_complete_sell_order(self, object sell_order_completed_event):
        self._did_complete_order(sell_order_completed_event)

    cdef c_did_fail_order(self, object fail_event):
        """
        Output log for failed order.

        :param fail_event: Order failure event
        """
        cdef:
            str order_id = fail_event.order_id
            object market_trading_pair_tuple = self._sb_order_tracker.c_get_market_pair_from_order_id(order_id)
        full_order = self._sb_order_tracker.c_get_limit_order(market_trading_pair_tuple, order_id)
        if fail_event.order_type is OrderType.LIMIT:
            # this code is still relevant
            self._failed_market_order_count += 1
            self._last_failed_market_order_timestamp = fail_event.timestamp

        if self._failed_market_order_count > self._failed_order_tolerance:
            failed_order_kill_switch_log = \
                f"Strategy is forced stop by failed order kill switch. " \
                f"Failed market order count {self._failed_market_order_count} exceeded tolerance level of " \
                f"{self._failed_order_tolerance}. Please check market connectivity before restarting."

            self.logger().network(failed_order_kill_switch_log, app_warning_msg=failed_order_kill_switch_log)
            self.c_stop(self._clock)
        if market_trading_pair_tuple is not None:
            self.log_with_clock(logging.INFO,
                                f"Limit order failed on {market_trading_pair_tuple[0].name}: {order_id}")
            if self._arbitrage_execution_tracker.reverse:
                self.log_with_clock(logging.WARNING,
                                    f"Order Failure on reversal order placed to unwind position. "
                                    f"Will continue to attempt to place. User action is strongly recommended.")
            else:
                self._arbitrage_execution_tracker.fail(market_trading_pair_tuple.trading_pair)
                self.log_with_clock(logging.INFO,
                                    f"Rewinding and pausing arbitrage")

    cdef c_did_fill_order(self, object order_filled_event):
        cdef:
            str order_id = order_filled_event.order_id
            object market_trading_pair_tuple = self._sb_order_tracker.c_get_market_pair_from_order_id(order_id)
            object market = market_trading_pair_tuple.market

        if market_trading_pair_tuple is not None:
            if self._logging_options & self.OPTION_LOG_ORDER_COMPLETED:
                self.log_with_clock(
                    logging.INFO,
                    f"Limit order filled on {market.name}: {order_id} ({order_filled_event.price}, {order_filled_event.amount})"
                )
            trading_pair = market_trading_pair_tuple.trading_pair
            self._arbitrage_execution_tracker.fill(trading_pair, order_filled_event.amount)

    cdef c_did_cancel_order(self, object cancel_event):
        """
        Output log for cancelled order.

        :param cancel_event: Order cancelled event.
        """
        cdef:
            str order_id = cancel_event.order_id
            object market_trading_pair_tuple = self._sb_order_tracker.c_get_market_pair_from_order_id(order_id)
        if market_trading_pair_tuple is not None:
            trading_pair = market_trading_pair_tuple.trading_pair
            self.log_with_clock(logging.INFO,
                                f"Limit order canceled on {market_trading_pair_tuple[0].name}: {order_id}")
            self._arbitrage_execution_tracker.cancel(trading_pair)
