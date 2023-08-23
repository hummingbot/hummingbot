from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorStatus
from hummingbot.smart_components.strategy_frameworks.executor_handler_base import ExecutorHandlerBase
from hummingbot.smart_components.strategy_frameworks.market_making.market_making_controller_base import (
    MarketMakingControllerBase,
)
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class MarketMakingExecutorHandler(ExecutorHandlerBase):
    def __init__(self, strategy: ScriptStrategyBase, controller: MarketMakingControllerBase,
                 update_interval: float = 1.0):
        super().__init__(strategy, controller, update_interval)
        self.controller = controller

    def on_stop(self):
        if self.controller.is_perpetual:
            self.close_open_positions(connector_name=self.controller.config.exchange, trading_pair=self.controller.config.trading_pair)
        super().on_stop()

    def on_start(self):
        if self.controller.is_perpetual:
            self.set_leverage_and_position_mode()

    def set_leverage_and_position_mode(self):
        connector = self.strategy.connectors[self.controller.config.exchange]
        connector.set_position_mode(self.controller.config.position_mode)
        connector.set_leverage(trading_pair=self.controller.config.trading_pair, leverage=self.controller.config.leverage)

    async def control_task(self):
        if self.controller.all_candles_ready:
            for order_level in self.controller.config.order_levels:
                current_executor = self.level_executors[order_level.level_id]
                if current_executor:
                    closed_and_not_in_cooldown = current_executor.is_closed and not self.controller.cooldown_condition(
                        current_executor, order_level)
                    active_and_early_stop_condition = current_executor.executor_status == PositionExecutorStatus.ACTIVE_POSITION and self.controller.early_stop_condition(
                        current_executor, order_level)
                    order_placed_and_refresh_condition = current_executor.executor_status == PositionExecutorStatus.NOT_STARTED and self.controller.refresh_order_condition(
                        current_executor, order_level)
                    if closed_and_not_in_cooldown:
                        self.store_executor(current_executor, order_level)
                    elif active_and_early_stop_condition or order_placed_and_refresh_condition:
                        current_executor.early_stop()
                else:
                    position_config = self.controller.get_position_config(order_level)
                    self.create_executor(position_config, order_level)
