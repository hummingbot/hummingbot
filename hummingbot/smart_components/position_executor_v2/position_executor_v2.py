from decimal import Decimal
from typing import List, Union

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.smart_components.position_executor.data_types import (
    PositionConfig,
    PositionExecutorStatus,
    TrackedOrder,
)
from hummingbot.smart_components.smart_component_base import SmartComponentBase
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class PositionExecutorV2(SmartComponentBase):
    def __init__(self, strategy: ScriptStrategyBase, connectors: List[str], position_config: PositionConfig):
        super().__init__(strategy, connectors)
        if not (position_config.take_profit or position_config.stop_loss or position_config.time_limit):
            error = "At least one of take_profit, stop_loss or time_limit must be set"
            self.logger().error(error)
            raise ValueError(error)
        self._position_config: PositionConfig = position_config
        self._close_type = None
        self._close_timestamp = None
        self._executor_status: PositionExecutorStatus = PositionExecutorStatus.NOT_STARTED

        # Order tracking
        self._open_order: TrackedOrder = TrackedOrder()
        self._close_order: TrackedOrder = TrackedOrder()
        # self._take_profit_order: TrackedOrder = TrackedOrder()
        # self._time_limit_order: TrackedOrder = TrackedOrder()
        # self._stop_loss_order: TrackedOrder = TrackedOrder()

    @property
    def executor_status(self):
        return self._executor_status

    @executor_status.setter
    def executor_status(self, status: PositionExecutorStatus):
        self._executor_status = status

    @property
    def position_config(self):
        return self._position_config

    @property
    def connector(self) -> ConnectorBase:
        return self.connectors[self._position_config.exchange]

    @property
    def exchange(self):
        return self.position_config.exchange

    @property
    def trading_pair(self):
        return self.position_config.trading_pair

    @property
    def amount(self):
        if self.open_order.executed_amount_base == Decimal("0"):
            return self.position_config.amount
        else:
            return self.open_order.executed_amount_base

    @property
    def entry_price(self):
        if not self.open_order.average_executed_price:
            entry_price = self.position_config.entry_price
            price = entry_price if entry_price else self.get_price(self.exchange, self.trading_pair)
        else:
            price = self.open_order.average_executed_price
        return price

    @property
    def close_price(self):
        if self.close_order.order:
            return self.close_order.average_executed_price

    @property
    def pnl(self):
        close_price = self.close_price if self.close_price else self.get_price(self.exchange, self.trading_pair)
        entry_price = self.entry_price if self.entry_price else self.get_price(self.exchange, self.trading_pair)
        if self.side == TradeType.BUY:
            return (close_price - entry_price) / entry_price
        else:
            return (entry_price - close_price) / entry_price

    @property
    def pnl_usd(self):
        return self.pnl * self.amount * self.entry_price

    @property
    def cum_fees(self):
        return self.open_order.cum_fees + self.close_order.cum_fees

    @property
    def end_time(self):
        return self.position_config.timestamp + self.position_config.time_limit

    @property
    def side(self):
        return self.position_config.side

    @property
    def open_order_type(self):
        return self.position_config.open_order_type

    @property
    def take_profit_order_type(self):
        return self.position_config.take_profit_order_type

    @property
    def stop_loss_order_type(self):
        return self.position_config.stop_loss_order_type

    @property
    def time_limit_order_type(self):
        return self.position_config.time_limit_order_type

    @property
    def stop_loss_price(self):
        stop_loss_price = self.entry_price * (1 - self._position_config.stop_loss) if self.side == TradeType.BUY else \
            self.entry_price * (1 + self._position_config.stop_loss)
        return stop_loss_price

    @property
    def take_profit_price(self):
        take_profit_price = self.entry_price * (1 + self._position_config.take_profit) if self.side == TradeType.SELL else \
            self.entry_price * (1 - self._position_config.take_profit)
        return take_profit_price

    @property
    def open_order(self):
        return self._open_order

    @property
    def close_order(self):
        return self._close_order

    def control_position(self):
        if self.executor_status == PositionExecutorStatus.NOT_STARTED:
            self.open_position()
        elif self.executor_status == PositionExecutorStatus.ACTIVE_POSITION:
            self.control_barriers()

    def open_position(self):
        if self.end_time >= self._strategy.current_timestamp:
            if not self.open_order.order_id:
                self.place_open_order()
            elif self.executor_status == PositionExecutorStatus.ORDER_PLACED:
                self.control_open_order_time_limit()
        else:
            self.executor_status = PositionExecutorStatus.CANCELED_BY_TIME_LIMIT

    def place_open_order(self):
        # TODO: Review filled order event to mark executor as active position
        order_id = self.place_order(
            connector_name=self.exchange,
            trading_pair=self.trading_pair,
            order_type=self.open_order_type,
            amount=self.amount,
            price=self.entry_price,
            trade_type=self.side,
            position_action=PositionAction.OPEN,
        )
        self._open_order.order_id = order_id
        self.logger().info("Placing open order")

    def control_open_order_time_limit(self):
        # TODO: Review cancel order event to mark smart component as terminated
        if self.end_time <= self._strategy.current_timestamp:
            self._strategy.cancel(
                connector_name=self.exchange,
                trading_pair=self.trading_pair,
                order_id=self._open_order.order_id
            )
            self.logger().info("Removing open order by time limit")

    def control_barriers(self):
        self.control_take_profit()
        self.control_stop_loss()
        self.control_time_limit()

    def control_take_profit(self):
        if not self.take_profit_order.order_id:
            if self.take_profit_condition() or self.take_profit_order_type != OrderType.MARKET:
                self.place_take_profit_order()
        elif self.take_profit_order.order and self.open_order.executed_amount_base != self.take_profit_order.order.amount:
            self.renew_take_profit_order()

    def take_profit_condition(self):
        if self.side == TradeType.BUY:
            return self.get_price(self.exchange, self.trading_pair) >= self.take_profit_price
        else:
            return self.get_price(self.exchange, self.trading_pair) <= self.take_profit_price

    def place_take_profit_order(self):
        price = self.get_price(self.exchange, self.trading_pair) if self.take_profit_order_type == OrderType.MARKET else self.take_profit_price
        order_id = self.place_order(
            connector_name=self._position_config.exchange,
            trading_pair=self._position_config.trading_pair,
            amount=self.open_order.executed_amount_base,
            price=price,
            order_type=self.take_profit_order_type,
            position_action=PositionAction.CLOSE,
            trade_type=TradeType.BUY if self.side == TradeType.SELL else TradeType.SELL,
        )
        self.take_profit_order.order_id = order_id
        self.logger().info("Placing take profit order")

    def renew_take_profit_order(self):
        self.remove_take_profit()
        self.place_take_profit_order()
        self.logger().info("Renewing take profit order")

    def remove_take_profit(self):
        self._strategy.cancel(
            connector_name=self.exchange,
            trading_pair=self.trading_pair,
            order_id=self._take_profit_order.order_id
        )
        self.logger().info("Removing take profit")

    def control_stop_loss(self):
        if self.stop_loss_condition() and not self.stop_loss_order.order_id and self.open_order.order:
            self.place_stop_loss_order()
            self.executor_status = PositionExecutorStatus.CLOSE_PLACED

    def stop_loss_condition(self):
        if self.side == TradeType.BUY:
            return self.get_price(self.exchange, self.trading_pair) <= self.stop_loss_price
        else:
            return self.get_price(self.exchange, self.trading_pair) >= self.stop_loss_price

    def place_stop_loss_order(self):
        # TODO: Implement order type for stop loss with limit order
        price = self.get_price(self.exchange, self.trading_pair)
        tp_partial_execution = self.take_profit_order.executed_amount_base if self.take_profit_order.executed_amount_base else Decimal("0")
        order_id = self.place_order(
            connector_name=self.exchange,
            trading_pair=self.trading_pair,
            amount=self.open_order.executed_amount_base - tp_partial_execution,
            price=price,
            order_type=OrderType.MARKET,
            position_action=PositionAction.CLOSE,
            trade_type=TradeType.BUY if self.side == TradeType.SELL else TradeType.SELL,
        )
        self.stop_loss_order.order_id = order_id
        self.logger().info("Placing stop loss order")

    def control_time_limit(self):
        if self.end_time < self._strategy.current_timestamp:
            if not self._time_limit_order.order_id and self.open_order.order:
                self.place_time_limit_order()
                self.executor_status = PositionExecutorStatus.CLOSE_PLACED

    def place_time_limit_order(self):
        # TODO: Implement order type for time limit with limit order
        price = self.get_price(self.exchange, self.trading_pair)
        tp_partial_execution = self.take_profit_order.executed_amount_base if self.take_profit_order.executed_amount_base else Decimal("0")
        order_id = self.place_order(
            connector_name=self.exchange,
            trading_pair=self.trading_pair,
            amount=self.open_order.executed_amount_base - tp_partial_execution,
            price=price,
            order_type=OrderType.MARKET,
            position_action=PositionAction.CLOSE,
            trade_type=TradeType.BUY if self.side == TradeType.SELL else TradeType.SELL,
        )
        self.time_limit_order.order_id = order_id
        self.logger().info("Placing time limit order")

    def process_order_completed_event(self, _, market, event: Union[BuyOrderCompletedEvent, SellOrderCompletedEvent]):
        if self.open_order.order_id == event.order_id:
            self.executor_status = PositionExecutorStatus.ACTIVE_POSITION
        elif self.stop_loss_order.order_id == event.order_id:
            self.executor_status = PositionExecutorStatus.CLOSED_BY_STOP_LOSS
            self.close_timestamp = event.timestamp
            self.logger().info("Closed by Stop loss")
        elif self.time_limit_order.order_id == event.order_id:
            self.executor_status = PositionExecutorStatus.CLOSED_BY_TIME_LIMIT
            self.close_timestamp = event.timestamp
            self.logger().info("Closed by Time Limit")
        elif self.take_profit_order.order_id == event.order_id:
            self.executor_status = PositionExecutorStatus.CLOSED_BY_TAKE_PROFIT
            self.close_timestamp = event.timestamp
            self.logger().info("Closed by Take Profit")

    def process_order_created_event(self, _, market, event: Union[BuyOrderCreatedEvent, SellOrderCreatedEvent]):
        if self.open_order.order_id == event.order_id:
            self.open_order.order = self.get_order(event.order_id)
            self.executor_status = PositionExecutorStatus.ORDER_PLACED
        elif self.take_profit_order.order_id == event.order_id:
            self.take_profit_order.order = self.get_order(event.order_id)
            self.logger().info("Take profit Created")
        elif self.stop_loss_order.order_id == event.order_id:
            self.logger().info("Stop loss Created")
            self.stop_loss_order.order = self.get_order(event.order_id)
        elif self.time_limit_order.order_id == event.order_id:
            self.logger().info("Time Limit Created")
            self.time_limit_order.order = self.get_order(event.order_id)

    def process_order_canceled_event(self, _, market, event: OrderCancelledEvent):
        if self.open_order.order_id == event.order_id:
            self.executor_status = PositionExecutorStatus.CANCELED_BY_TIME_LIMIT
            self.close_timestamp = event.timestamp

    def process_order_filled_event(self, _, market, event: OrderFilledEvent):
        if self.open_order.order_id == event.order_id:
            if self.executor_status == PositionExecutorStatus.ACTIVE_POSITION:
                self.logger().info("Position incremented, updating take profit next tick.")
            else:
                self.executor_status = PositionExecutorStatus.ACTIVE_POSITION

    def process_order_failed_event(self, _, market, event: MarketOrderFailureEvent):
        if self.open_order.order_id == event.order_id:
            self.place_open_order()
            self.executor_status = PositionExecutorStatus.NOT_STARTED
        elif self.stop_loss_order.order_id == event.order_id:
            self.place_stop_loss_order()
        elif self.time_limit_order.order_id == event.order_id:
            self.place_time_limit_order()
        elif self.take_profit_order.order_id == event.order_id:
            self.place_take_profit_order()
