from typing import Union

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.strategy_v2.executors.progressive_executor.protocols import (
    OrderManagementProtocol,
    ProgressiveOrderProcessProtocol,
    ProgressiveOrderProtocol,
)


class OrderProcessingMixin:
    def process_order_created_event(
        self: OrderManagementProtocol, _, market, event: Union[BuyOrderCreatedEvent, SellOrderCreatedEvent]
    ):
        self.update_tracked_orders_with_order_id(event.order_id)

    def process_order_completed_event(
        self: ProgressiveOrderProtocol, _, market, event: Union[BuyOrderCompletedEvent, SellOrderCompletedEvent]
    ):
        if self.close_order and self.close_order.order_id == event.order_id:
            self.close_timestamp = event.timestamp

    def process_order_filled_event(self: ProgressiveOrderProtocol, _, market, event: OrderFilledEvent):
        if self.open_order and event.order_id == self.open_order.order_id:
            self.total_executed_amount_backup += event.amount
        elif event.order_id in [order.order_id for order in self.realized_orders]:
            self.total_executed_amount_backup -= event.amount
        elif self.close_order and event.order_id == self.close_order.order_id:
            self.total_executed_amount_backup -= event.amount
        self.update_tracked_orders_with_order_id(event.order_id)

    def process_order_canceled_event(
        self: ProgressiveOrderProtocol,
        _,
        market: ConnectorBase,
        event: OrderCancelledEvent,
    ):
        if self.close_order and event.order_id == self.close_order.order_id:
            self.canceled_orders.append(self.close_order)
            self.close_order = None
        elif any(event.order_id == order.order_id for order in self.realized_orders):
            self.canceled_orders.append(
                next(order for order in self.realized_orders if order.order_id == event.order_id)
            )
            self.realized_orders = [order for order in self.realized_orders if order.order_id != event.order_id]

    def process_order_failed_event(
        self: ProgressiveOrderProcessProtocol,
        _,
        market: ConnectorBase,
        event: MarketOrderFailureEvent,
    ):
        self.current_retries += 1
        if self.open_order and event.order_id == self.open_order.order_id:
            self.failed_orders.append(self.open_order)
            self.open_order = None
            self.logger().error(f"Open order failed. Retrying {self.current_retries}/{self.max_retries}")
        elif self.close_order and event.order_id == self.close_order.order_id:
            self.failed_orders.append(self.close_order)
            self.close_order = None
            self.logger().error(f"Close order failed. Retrying {self.current_retries}/{self.max_retries}")
        elif any(event.order_id == order.order_id for order in self.realized_orders):
            self.failed_orders.append(next(order for order in self.realized_orders if order.order_id == event.order_id))
            self.realized_orders = [order for order in self.realized_orders if order.order_id != event.order_id]
