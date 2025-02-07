import asyncio
import logging
from typing import Union

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    SellOrderCompletedEvent,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.position_executor.position_executor import PositionExecutor
from hummingbot.strategy_v2.executors.position_on_exchange_executor.data_types import PositionOnExchangeExecutorConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder


class PositionOnExchangeExecutor(PositionExecutor):
    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(
            self,
            strategy: ScriptStrategyBase,
            config: PositionOnExchangeExecutorConfig,
            update_interval: float = 1.0,
            max_retries: int = 10
    ):
        """
        Initialize the PositionOnExchangeExecutor instance.

        :param strategy: The strategy to be used by the PositionOnExchangeExecutor.
        :param config: The configuration for the PositionOnExchangeExecutor, subclass of PositionExecutoConfig.
        :param update_interval: The interval at which the PositionOnExchangeExecutor should be updated, defaults to 1.0.
        :param max_retries: The maximum number of retries for the PositionOnExchangeExecutor, defaults to 5.
        """
        if (
            config.triple_barrier_config.time_limit_order_type != OrderType.MARKET
            or config.triple_barrier_config.stop_loss_order_type != OrderType.STOP_LOSS
            or config.triple_barrier_config.take_profit_order_type == OrderType.MARKET
        ):
            error = "Only market orders are supported for time_limit. Stop-loss & Take-profit/limit orders accordingly"
            self.logger().error(error)
            raise ValueError(error)
        # Bypass exception on non-market stop_limit_order_type
        position_config = config
        position_config.triple_barrier_config.stop_loss_order_type = OrderType.MARKET
        super().__init__(strategy=strategy, config=position_config, update_interval=update_interval)
        self.config.triple_barrier_config.stop_loss_order_type = OrderType.STOP_LOSS

        self._stop_loss_order: TrackedOrder | None = None
        self._take_profit_order: TrackedOrder | None = None

    @property
    def stop_loss_price(self):
        """
        This method is responsible for calculating the take profit price to place the take profit limit order.

        :return: The take profit price.
        """
        if self.config.side == TradeType.BUY:
            stop_loss_price = self.entry_price * (1 - self.config.triple_barrier_config.stop_loss)
        else:
            stop_loss_price = self.entry_price * (1 + self.config.triple_barrier_config.stop_loss)
        return stop_loss_price

    def control_stop_loss(self):
        """
        This method is responsible for controlling the stop loss. If the net pnl percentage is less than the stop loss
        percentage, it places the close order and cancels the open orders.

        :return: None
        """
        if self.config.triple_barrier_config.stop_loss and not self._stop_loss_order:
            self.place_stop_loss_order()

    def control_take_profit(self):
        """
        This method is responsible for controlling the take profit. If the net pnl percentage is greater than the take
        profit percentage, it places the close order and cancels the open orders. If the take profit order type is limit,
        it places the take profit limit order. If the amount of the take profit order is different than the total amount
        executed in the open order, it renews the take profit order (can happen with partial fills).

        :return: None
        """
        if self.config.triple_barrier_config.take_profit and not self._take_profit_order:
            if self.config.triple_barrier_config.take_profit_order_type.is_limit_type():
                is_within_activation_bounds = self._is_within_activation_bounds(
                    self.take_profit_price, self.close_order_side,
                    self.config.triple_barrier_config.take_profit_order_type)
                if not self._take_profit_limit_order:
                    if is_within_activation_bounds:
                        self.place_take_profit_limit_order()
                else:
                    if self._take_profit_limit_order.is_open and not self._take_profit_limit_order.is_filled and \
                            not is_within_activation_bounds:
                        self.cancel_take_profit()
            else:
                self.place_take_profit_order()

    def place_stop_loss_order(self):
        """
        This method is responsible for placing the take profit limit order.

        :return: None
        """
        if not self._stop_loss_order:
            order_id = self.place_order(
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                amount=self.amount_to_close,
                price=self.stop_loss_price,
                order_type=OrderType.STOP_LOSS,
                position_action=PositionAction.CLOSE,
                side=self.close_order_side,
            )
            self._stop_loss_order = TrackedOrder(order_id=order_id)
            self.logger().debug(f"Executor ID: {self.config.id} - Placing stop loss order {order_id}")
        else:
            self.logger().debug(f"Executor ID: {self.config.id} - Stop loss order already placed")

    def place_take_profit_order(self):
        """
        This method is responsible for placing the take profit limit order.

        :return: None
        """
        if not self._take_profit_order and not self._take_profit_limit_order:
            order_id = self.place_order(
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                amount=self.amount_to_close,
                price=self.take_profit_price,
                order_type=OrderType.TAKE_PROFIT,
                position_action=PositionAction.CLOSE,
                side=self.close_order_side,
            )
            self._take_profit_order = TrackedOrder(order_id=order_id)
            self.logger().debug(f"Executor ID: {self.config.id} - Placing take profit order {order_id}")
        elif self._take_profit_limit_order:
            raise ValueError("Take profit limit order attempt while a limit order is already in place")
        else:
            self.logger().debug(f"Executor ID: {self.config.id} - Take profit order already placed")

    def renew_stop_loss_order(self):
        """
        This method is responsible for renewing the stop loss order.

        :return: None
        """
        self.cancel_stop_loss()
        self.place_stop_loss_order()
        self.logger().debug("Renewing stop loss order")

    def renew_take_profit_order(self):
        """
        This method is responsible for renewing the take profit order.

        :return: None
        """
        self.cancel_take_profit()
        if self._take_profit_limit_order:
            self.place_take_profit_limit_order()
        else:
            self.place_take_profit_order()
        self.logger().debug("Renewing take profit order")

    def cancel_stop_loss(self):
        """
        This method is responsible for canceling the take profit order.

        :return: None
        """
        self._strategy.cancel(
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            order_id=self._stop_loss_order.order_id
        )
        self.logger().debug("Removing stop loss")

    def cancel_open_orders(self):
        """
        This method is responsible for canceling the open orders.

        :return: None
        """
        super().cancel_open_orders()
        if self._take_profit_order and self._take_profit_order.order and self._take_profit_order.order.is_open:
            self.cancel_take_profit()
        if self._stop_loss_order and self._stop_loss_order.order and self._stop_loss_order.order.is_open:
            self.cancel_stop_loss()

    def cancel_take_profit(self):
        """
        This method is responsible for canceling the take profit order.

        :return: None
        """
        self._strategy.cancel(
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            order_id=self._take_profit_order.order_id
        )
        self.logger().debug("Removing take profit")

    def cancel_open_order(self):
        """
        This method is responsible for canceling the open order.

        :return: None
        """
        self._strategy.cancel(
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            order_id=self._open_order.order_id
        )
        self.logger().debug("Removing open order")

    def update_tracked_orders_with_order_id(self, order_id: str):
        """
        This method is responsible for updating the tracked orders with the information from the InFlightOrder, using
        the order_id as a reference.

        :param order_id: The order_id to be used as a reference.
        :return: None
        """
        in_flight_order = self.get_in_flight_order(self.config.connector_name, order_id)
        super().update_tracked_orders_with_order_id(order_id)

        if self._stop_loss_order and self._stop_loss_order.order_id == order_id:
            self._stop_loss_order.order = in_flight_order
        if self._take_profit_order and self._take_profit_order.order_id == order_id:
            self._take_profit_order.order = in_flight_order

    def process_order_completed_event(self, _, market, event: Union[BuyOrderCompletedEvent, SellOrderCompletedEvent]):
        """
        This method is responsible for processing the order completed event. Here we will check if the id is one of the
        tracked orders and update the state
        """
        self._total_executed_amount_backup += event.base_asset_amount
        self.update_tracked_orders_with_order_id(event.order_id)
        super().process_order_completed_event(_, market, event)

        if self._stop_loss_order and self._stop_loss_order.order_id == event.order_id:
            self.close_type = CloseType.STOP_LOSS
            self._close_order = self._stop_loss_order
            self._status = RunnableStatus.SHUTTING_DOWN
        if self._take_profit_order and self._take_profit_order.order_id == event.order_id:
            self.close_type = CloseType.TAKE_PROFIT
            self._close_order = self._take_profit_order
            self._status = RunnableStatus.SHUTTING_DOWN

    def process_order_canceled_event(self, _, market: ConnectorBase, event: OrderCancelledEvent):
        """
        This method is responsible for processing the order canceled event
        """
        super().process_order_canceled_event(_, market, event)
        if self._stop_loss_order and event.order_id == self._stop_loss_order.order_id:
            self._failed_orders.append(self._stop_loss_order)
            self._stop_loss_order = None
        if self._take_profit_order and event.order_id == self._take_profit_order.order_id:
            self._failed_orders.append(self._take_profit_order)
            self._take_profit_order = None

    def process_order_failed_event(self, _, market, event: MarketOrderFailureEvent):
        """
        This method is responsible for processing the order failed event. Here we will add the InFlightOrder to the
        failed orders list.
        """
        super().process_order_failed_event(_, market, event)
        if self._stop_loss_order and event.order_id == self._stop_loss_order.order_id:
            self._failed_orders.append(self._stop_loss_order)
            self._stop_loss_order = None
            self.logger().error(
                f"Stop loss order failed {event.order_id}. Retrying {self._current_retries}/{self._max_retries}")
        if self._take_profit_order and event.order_id == self._take_profit_order.order_id:
            self._failed_orders.append(self._take_profit_order)
            self._take_profit_order = None
            self.logger().error(
                f"Take profit order failed {event.order_id}. Retrying {self._current_retries}/{self._max_retries}")

    async def _sleep(self, delay: float):
        """
        This method is responsible for sleeping the executor for a specific time.

        :param delay: The time to sleep.
        :return: None
        """
        await asyncio.sleep(delay)
