import asyncio
import logging
from decimal import Decimal
from typing import Dict, Optional, Union

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import PositionAction, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate, PerpetualOrderCandidate
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.executor_base import ExecutorBase
from hummingbot.strategy_v2.executors.twap_executor.data_types import TWAPExecutorConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder


class TWAPExecutor(ExecutorBase):
    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, strategy: ScriptStrategyBase, config: TWAPExecutorConfig, update_interval: float = 1.0,
                 max_retries: int = 15):
        super().__init__(strategy=strategy, connectors=[config.connector_name], config=config, update_interval=update_interval)
        self.config = config
        trading_rules = self.get_trading_rules(config.connector_name, config.trading_pair)
        if self.config.order_amount_quote < trading_rules.min_order_size:
            self.close_execution_by(CloseType.FAILED)
            self.logger().error("Please increase the total amount or the interval between orders. The current"
                                f"amount {self.config.order_amount_quote} is less than the minimum order {trading_rules.min_order_size}")
        if self.config.is_maker:
            self.logger().warning("Maker mode is in beta. Please use with caution.")
        self._max_retries = max_retries
        self._current_retries = 0
        self._start_timestamp = self._strategy.current_timestamp
        self._order_plan: Dict[float, Optional[TrackedOrder]] = self.create_order_plan()
        self._failed_orders = []
        self._refreshed_orders = []

    def create_order_plan(self):
        order_plan = {}
        for i in range(self.config.number_of_orders):
            timestamp = self._start_timestamp + i * self.config.order_interval
            order_plan[timestamp] = None  # Initialized with None, to be replaced with a TrackedOrder
        return order_plan

    def close_execution_by(self, close_type):
        self.close_type = close_type
        self.close_timestamp = self._strategy.current_timestamp
        self.stop()

    def validate_sufficient_balance(self):
        mid_price = self.get_price(self.config.connector_name, self.config.trading_pair, PriceType.MidPrice)
        total_amount_base = self.config.total_amount_quote / mid_price
        if self.is_perpetual_connector(self.config.connector_name):
            order_candidate = PerpetualOrderCandidate(
                trading_pair=self.config.trading_pair,
                is_maker=self.config.is_maker,
                order_type=self.config.order_type,
                order_side=self.config.side,
                amount=total_amount_base,
                price=mid_price,
                leverage=Decimal(self.config.leverage),
            )
        else:
            order_candidate = OrderCandidate(
                trading_pair=self.config.trading_pair,
                is_maker=self.config.is_maker,
                order_type=self.config.order_type,
                order_side=self.config.side,
                amount=total_amount_base,
                price=mid_price,
            )
        adjusted_order_candidates = self.adjust_order_candidates(self.config.connector_name, [order_candidate])
        if adjusted_order_candidates[0].amount == Decimal("0"):
            self.close_type = CloseType.INSUFFICIENT_BALANCE
            self.logger().error("Not enough budget to open position.")
            self.stop()

    async def control_task(self):
        if self.status == RunnableStatus.RUNNING:
            self.evaluate_create_order()
            self.evaluate_refresh_orders()
            self.evaluate_all_orders_completed()
            self.evaluate_max_retries()
        elif self.status == RunnableStatus.SHUTTING_DOWN:
            await self.evaluate_all_orders_closed()

    def evaluate_create_order(self):
        for timestamp, tracked_order in self._order_plan.items():
            if self._strategy.current_timestamp >= timestamp and tracked_order is None:
                self.create_order(timestamp)

    def evaluate_refresh_orders(self):
        if self.config.is_maker:
            for timestamp, tracked_order in self._order_plan.items():
                if self.refresh_order_condition(tracked_order):
                    self._strategy.cancel(self.config.connector_name, self.config.trading_pair, tracked_order.order_id)
                    self._refreshed_orders.append(tracked_order)
                    self.create_order(timestamp)

    def refresh_order_condition(self, tracked_order: TrackedOrder):
        if self.config.order_resubmission_time:
            return tracked_order and tracked_order.order and tracked_order.order.is_open \
                and tracked_order.order.creation_timestamp \
                < self._strategy.current_timestamp - self.config.order_resubmission_time
        else:
            return False

    def evaluate_max_retries(self):
        if self._current_retries > self._max_retries:
            self.close_execution_by(CloseType.FAILED)

    def create_order(self, timestamp):
        price = self.get_price(self.config.connector_name, self.config.trading_pair, PriceType.MidPrice)
        total_executed_amount = self.get_total_executed_amount_quote()
        open_orders_open_amount = sum([order.order.amount * order.order.price for order in self._order_plan.values() if order and order.order and not order.is_done])
        orders_amount_quote_left = self.config.total_amount_quote - total_executed_amount - open_orders_open_amount
        number_or_orders_left = self.config.number_of_orders - len([order for order in self._order_plan.values() if order])
        amount = (orders_amount_quote_left / number_or_orders_left) / price
        if self.config.is_maker:
            order_price = price * (1 + self.config.limit_order_buffer) if self.config.side == TradeType.SELL else price * (1 - self.config.limit_order_buffer)
        else:
            order_price = price
        order_id = self.place_order(
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            order_type=self.config.order_type,
            side=self.config.side,
            amount=amount,
            price=order_price,
            position_action=PositionAction.OPEN
        )
        self._order_plan[timestamp] = TrackedOrder(order_id=order_id)

    def process_order_created_event(self,
                                    event_tag: int,
                                    market: ConnectorBase,
                                    event: Union[BuyOrderCreatedEvent, SellOrderCreatedEvent]):
        """
        This method is responsible for processing the order created event. Here we will add the InFlightOrder to the
        active orders list.
        """
        self.update_tracked_orders_with_order_id(event.order_id)

    def process_order_failed_event(self,
                                   event_tag: int,
                                   market: ConnectorBase,
                                   event: MarketOrderFailureEvent):
        """
        This method is responsible for processing the order failed event. Here we will check if the order id is one of
        the order plan and if it is we will move the order to the failed collection and retry with a new order.
        """
        all_orders = self._order_plan.values()
        active_order = next((order for order in all_orders if order.order_id == event.order_id), None)
        if active_order:
            self._failed_orders.append(active_order)
            self._order_plan = {timestamp: None for timestamp, order in self._order_plan.items() if order == active_order}
            self._current_retries += 1

    def update_tracked_orders_with_order_id(self, order_id: str):
        all_orders = self._order_plan.values()
        active_order = next((order for order in all_orders if order.order_id == order_id), None)
        if active_order:
            in_flight_order = self.get_in_flight_order(self.config.connector_name, order_id)
            if in_flight_order:
                active_order.order = in_flight_order

    def process_order_completed_event(self,
                                      event_tag: int,
                                      market: ConnectorBase,
                                      event: Union[BuyOrderCompletedEvent, SellOrderCompletedEvent]):
        """
        This method is responsible for processing the order completed event. Here we will check if the order id is one
        of the order plan and if it is we will check if the rest of the orders are completed and if they are we will
        pass the executor to SHUTTING_DOWN state.
        """
        active_order = next((order for order in self._order_plan.values() if order.order_id == event.order_id), None)
        if active_order:
            self.evaluate_all_orders_completed()

    def evaluate_all_orders_completed(self):
        if self.evaluate_all_orders_created():
            if all([order.order.is_filled for order in self._order_plan.values() if order and order.order]):
                self._status = RunnableStatus.SHUTTING_DOWN

    def evaluate_all_orders_created(self):
        return all([order for order in self._order_plan.values()])

    async def evaluate_all_orders_closed(self):
        refreshed_orders_done = all([order.is_done for order in self._refreshed_orders])
        failed_orders_done = all([order.is_done for order in self._failed_orders])
        if refreshed_orders_done and failed_orders_done:
            self.close_execution_by(CloseType.COMPLETED)
            self._status = RunnableStatus.TERMINATED
        else:
            self._current_retries += 1
            await asyncio.sleep(5)

    def cancel_open_orders(self):
        for order in self._order_plan.values():
            if order and order.order and order.order.is_open:
                self._strategy.cancel(self.config.connector_name, self.config.trading_pair, order.order_id)

    def early_stop(self):
        self.close_execution_by(CloseType.EARLY_STOP)
        self.cancel_open_orders()
        self._status = RunnableStatus.SHUTTING_DOWN
        self.logger().info("Executor stopped early.")

    @property
    def filled_amount_quote(self) -> Decimal:
        return self.get_total_executed_amount_quote()

    @property
    def trade_pnl_pct(self) -> Decimal:
        """
        Calculate the trade pnl (Pure pnl without fees)

        :return: The trade pnl percentage.
        """
        mid_price = self.get_price(self.config.connector_name, self.config.trading_pair, PriceType.MidPrice)
        average_executed_price = self.get_average_executed_price()
        if average_executed_price != Decimal("0"):
            if self.config.side == TradeType.BUY:
                return (mid_price - average_executed_price) / average_executed_price
            else:
                return (average_executed_price - mid_price) / average_executed_price
        else:
            return Decimal("0")

    @property
    def trade_pnl_quote(self) -> Decimal:
        """
        This method is responsible for calculating the trade pnl in quote asset
        """
        return self.trade_pnl_pct * self.get_total_executed_amount_quote()

    def get_cum_fees_quote(self) -> Decimal:
        """
        This method is responsible for calculating the cumulative fees in quote asset
        """
        return sum([order.cum_fees_quote for order in self._order_plan.values() if order])

    def get_net_pnl_quote(self) -> Decimal:
        """
        This method is responsible for calculating the net pnl in quote asset
        """
        return self.trade_pnl_quote - self.cum_fees_quote

    def get_net_pnl_pct(self) -> Decimal:
        """
        This method is responsible for calculating the net pnl percentage
        """
        total_executed_quote = self.get_total_executed_amount_quote()
        return self.net_pnl_quote / total_executed_quote if total_executed_quote > Decimal("0") else Decimal("0")

    def get_average_executed_price(self) -> Decimal:
        """
        Get the weighted average executed price of the orders.
        """
        total_executed_amount = self.get_total_executed_amount()
        if total_executed_amount == Decimal("0"):
            return Decimal("0")
        return sum([order.average_executed_price * order.executed_amount_base for order in self._order_plan.values() if order]) / total_executed_amount

    def get_total_executed_amount(self) -> Decimal:
        """
        Get the total executed amount of the orders.
        """
        return sum([order.executed_amount_base for order in self._order_plan.values() if order])

    def get_total_executed_amount_quote(self) -> Decimal:
        """
        Get the total executed amount of the orders in quote asset.
        """
        return self.get_total_executed_amount() * self.get_average_executed_price()
