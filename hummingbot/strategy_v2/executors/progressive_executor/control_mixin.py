import asyncio
import functools
import math

from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType

from .protocols import (
    ProgressiveControlProtocol,
    ProgressiveOrderControlProtocol,
    ProgressiveOrderExecutionPNLControlProtocol,
)


class ControlMixin:
    async def control_task(self: ProgressiveControlProtocol):
        if self.status == RunnableStatus.RUNNING:
            self.control_failed_orders()
            self.control_open_order()
            self.control_barriers()
        elif self.status == RunnableStatus.SHUTTING_DOWN:
            self.logger().info(
                f"Executor shutting down | close_type={self.close_type} "
                f"open_filled={self.open_filled_amount:.6f} close_filled={self.close_filled_amount:.6f} "
                f"retries={self.current_retries}/{self.max_retries}"
            )
            await self.control_shutdown_process()
        self.evaluate_max_retries()

    def control_barriers(self: ProgressiveControlProtocol):
        self.control_stop_loss()
        self.control_trailing_stop()
        self.control_time_limit()

    async def control_shutdown_process(self: ProgressiveOrderControlProtocol):
        if math.isclose(self.open_filled_amount, self.close_filled_amount, rel_tol=1e-2):
            if self.open_orders_completed():
                self.stop()
            else:
                self.cancel_open_orders()
                self.current_retries += 1
        elif self.close_order:
            if self.current_retries < self.max_retries / 2:
                self.logger().info(
                    f"Waiting for close order to be filled --> Filled amount: {self.close_filled_amount} | Open amount: {self.open_filled_amount}"
                )
            else:
                self.logger().info("No fill on close order, will be retried.")
                self.cancel_close_order()
                self.current_retries += 1
        else:
            self.logger().info(f"Open amount: {self.open_filled_amount}, Close amount: {self.close_filled_amount}")
            self.place_close_order_and_cancel_open_orders(close_type=self.close_type)
            self.current_retries += 1
        await asyncio.sleep(2.0)

    def control_failed_orders(self: ProgressiveOrderControlProtocol):
        pass

    def control_open_order(self: ProgressiveOrderControlProtocol):
        if not self.open_order and self._is_within_activation_bounds(self.close_price):
            self.logger().info(
                f"Opening {self.config.side.name} | pair={self.config.trading_pair} "
                f"entry={self.entry_price:.6g} amount={self.config.amount:.6g} "
                f"SL={self.config.triple_barrier_config.stop_loss} "
                f"TL={self.config.triple_barrier_config.time_limit}"
            )
            self.place_open_order()

    def control_stop_loss(self: ProgressiveOrderExecutionPNLControlProtocol):
        if self.config.triple_barrier_config.stop_loss:
            target = self.get_target_pnl_yield() - self.config.triple_barrier_config.stop_loss
            if self.net_pnl_pct <= target:
                self.logger().info(f"STOP LOSS triggered | pnl={self.net_pnl_pct:.4%} threshold={target:.4%}")
                self.place_close_order_and_cancel_open_orders(close_type=CloseType.STOP_LOSS)

    def control_time_limit(self: ProgressiveOrderExecutionPNLControlProtocol):
        if self.is_expired and not self.is_extended_on_yield:
            self.logger().info(
                f"TIME LIMIT triggered | pnl={self.net_pnl_pct:.4%} extended_on_yield={self.is_extended_on_yield}"
            )
            self.place_close_order_and_cancel_open_orders(close_type=CloseType.TIME_LIMIT)

    def control_trailing_stop(self: ProgressiveOrderExecutionPNLControlProtocol):
        if not self.config.triple_barrier_config.trailing_stop:
            return

        if self.open_filled_amount > 0:
            self.trailing_stop_manager.update(
                net_pnl_pct=self.get_net_pnl_pct(),
                current_amount=self.open_filled_amount,
                on_close_position=functools.partial(
                    self.place_close_order_and_cancel_open_orders, close_type=CloseType.TRAILING_STOP
                ),
                on_partial_close=functools.partial(self.place_partial_close_order, close_type=CloseType.TRAILING_STOP),
            )

    def evaluate_max_retries(self: ProgressiveOrderControlProtocol):
        if self.current_retries > self.max_retries:
            self.logger().warning(
                f"Max retries exceeded ({self.current_retries}/{self.max_retries}) | closing as FAILED"
            )
            self.close_type = CloseType.FAILED
            self.stop()
