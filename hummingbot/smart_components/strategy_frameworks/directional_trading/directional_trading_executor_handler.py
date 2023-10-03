from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorStatus
from hummingbot.smart_components.strategy_frameworks.directional_trading.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
)
from hummingbot.smart_components.strategy_frameworks.executor_handler_base import ExecutorHandlerBase
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DirectionalTradingExecutorHandler(ExecutorHandlerBase):
    def __init__(self, strategy: ScriptStrategyBase, controller: DirectionalTradingControllerBase,
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
            signal = self.controller.get_signal()
            if signal != 0:
                for order_level in self.controller.config.order_levels:
                    current_executor = self.level_executors[order_level.level_id]
                    if current_executor:
                        closed_and_not_in_cooldown = current_executor.is_closed and not self.controller.cooldown_condition(current_executor, order_level)
                        active_and_early_stop_condition = current_executor.executor_status == PositionExecutorStatus.ACTIVE_POSITION and self.controller.early_stop_condition(current_executor, order_level)
                        if closed_and_not_in_cooldown:
                            self.store_executor(current_executor, order_level)
                        elif active_and_early_stop_condition:
                            current_executor.early_stop()
                    else:
                        position_config = self.controller.get_position_config(order_level, signal)
                        if position_config:
                            self.create_executor(position_config, order_level)
