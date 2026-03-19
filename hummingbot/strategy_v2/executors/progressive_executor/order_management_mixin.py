from decimal import Decimal

from hummingbot.strategy_v2.executors.progressive_executor.protocols import ProgressiveOrderProtocol


class OrderManagementMixin:
    @property
    def open_filled_amount(self: ProgressiveOrderProtocol) -> Decimal:
        return self.open_order.executed_amount_base if self.open_order else Decimal("0")

    @property
    def open_filled_amount_quote(self: ProgressiveOrderProtocol) -> Decimal:
        return self.open_filled_amount * self.entry_price

    def open_orders_completed(self: ProgressiveOrderProtocol) -> bool:
        open_order_condition = not self.open_order or self.open_order.is_done
        failed_orders_condition = not self.failed_orders or all(order.is_done for order in self.failed_orders)
        return open_order_condition and failed_orders_condition

    @property
    def realized_filled_amount(self: ProgressiveOrderProtocol) -> Decimal:
        return sum(
            (order.executed_amount_base for order in self.realized_orders),
            start=Decimal("0"),
        )

    @property
    def unrealized_filled_amount(self) -> Decimal:
        return self.open_filled_amount - self.realized_filled_amount

    @property
    def close_filled_amount(self: ProgressiveOrderProtocol) -> Decimal:
        return self.close_order.executed_amount_base if self.close_order else Decimal("0")

    @property
    def close_filled_amount_quote(self: ProgressiveOrderProtocol) -> Decimal:
        return self.close_filled_amount * self.close_price

    @property
    def filled_amount(self) -> Decimal:
        return self.open_filled_amount + self.close_filled_amount + self.realized_filled_amount

    @property
    def filled_amount_quote(self) -> Decimal:
        return self.open_filled_amount_quote + self.close_filled_amount_quote

    def update_tracked_orders_with_order_id(self: ProgressiveOrderProtocol, order_id: str):
        if self.open_order and self.open_order.order_id == order_id:
            self.open_order.order = self.get_in_flight_order(self.config.connector_name, order_id)
        elif self.close_order and self.close_order.order_id == order_id:
            self.close_order.order = self.get_in_flight_order(self.config.connector_name, order_id)
        else:
            for order in self.realized_orders:
                if order.order_id == order_id:
                    order.order = self.get_in_flight_order(self.config.connector_name, order_id)
