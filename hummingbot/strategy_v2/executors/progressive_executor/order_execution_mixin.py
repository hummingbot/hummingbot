from decimal import Decimal

from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType
from hummingbot.strategy_v2.executors.progressive_executor.protocols import (
    ProgressiveOrderExecutionProtocol,
    ProgressiveOrderProtocol,
)
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder


class OrderExecutionMixin:
    def place_open_order(self: ProgressiveOrderProtocol) -> None:
        order_id = self.place_order(
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            order_type=self.config.triple_barrier_config.open_order_type,
            amount=self.config.amount,
            price=self.entry_price,
            side=self.config.side,
            position_action=PositionAction.OPEN,
        )
        self.logger().info(
            f"Open order placed | id={order_id} type={self.config.triple_barrier_config.open_order_type.name} "
            f"price={self.entry_price:.6g} amount={self.config.amount:.6g}")
        self.open_order = TrackedOrder(order_id=order_id)
        self.open_order_timestamp = self.current_timestamp

    def place_close_order_and_cancel_open_orders(
            self: ProgressiveOrderExecutionProtocol,
            close_type: CloseType,
            price: Decimal = Decimal("NaN")
    ):
        delta_amount_to_close = self.unrealized_filled_amount - self.close_filled_amount
        trading_rules = self.get_trading_rules(self.config.connector_name, self.config.trading_pair)
        self.cancel_open_orders()
        if delta_amount_to_close > trading_rules.min_order_size:
            try:
                order_id = self.place_order(
                    connector_name=self.config.connector_name,
                    trading_pair=self.config.trading_pair,
                    order_type=OrderType.MARKET,
                    amount=delta_amount_to_close,
                    price=price,
                    side=TradeType.SELL if self.config.side == TradeType.BUY else TradeType.BUY,
                    position_action=PositionAction.CLOSE,
                )
                self.close_order = TrackedOrder(order_id=order_id)
                self.logger().info(
                    f"Close order placed | id={order_id} type={close_type.name} "
                    f"amount={delta_amount_to_close:.6g} filled_open={self.open_filled_amount:.6g}")
            except Exception as e:
                self.logger().error(f"Failed to place close order: {e}")

        self.close_type = close_type
        self.close_timestamp = self.current_timestamp
        self._status = RunnableStatus.SHUTTING_DOWN

    def place_partial_close_order(
            self: ProgressiveOrderExecutionProtocol,
            close_type: CloseType,
            price: Decimal = Decimal("NaN"),
            amount_to_close: Decimal = Decimal("NaN")
    ) -> None:
        if amount_to_close >= self.unrealized_filled_amount:
            self.place_close_order_and_cancel_open_orders(close_type=close_type, price=price)
            return

        trading_rules = self.get_trading_rules(self.config.connector_name, self.config.trading_pair)
        if amount_to_close > trading_rules.min_order_size:
            try:
                order_id = self.place_order(
                    connector_name=self.config.connector_name,
                    trading_pair=self.config.trading_pair,
                    order_type=OrderType.MARKET,
                    amount=amount_to_close,
                    price=price,
                    side=TradeType.SELL if self.config.side == TradeType.BUY else TradeType.BUY,
                    position_action=PositionAction.NIL,
                )
                self.realized_orders.append(TrackedOrder(order_id=order_id))
                self.logger().debug(f"Placing partial close order --> Filled amount: {amount_to_close}")
            except Exception as e:
                self.logger().error(f"Failed to place partial close order: {e}")

    def cancel_open_order(self: ProgressiveOrderProtocol) -> None:
        self.strategy.cancel(
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            order_id=self.open_order.order_id
        )
        self.logger().debug("Removing open order")

    def cancel_close_order(self: ProgressiveOrderProtocol) -> None:
        self.strategy.cancel(
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            order_id=self.close_order.order_id
        )
        self.logger().debug("Removing close order")

    def cancel_open_orders(self: ProgressiveOrderExecutionProtocol) -> None:
        if self.open_order and self.open_order.order and self.open_order.order.is_open:
            self.cancel_open_order()
