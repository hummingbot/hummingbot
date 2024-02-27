import time
from typing import List, Optional, Union

from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.smart_components.executors.arbitrage_executor.arbitrage_executor import ArbitrageExecutor
from hummingbot.smart_components.executors.arbitrage_executor.data_types import ArbitrageExecutorConfig
from hummingbot.smart_components.executors.dca_executor.data_types import DCAExecutorConfig
from hummingbot.smart_components.executors.dca_executor.dca_executor import DCAExecutor
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.smart_components.executors.position_executor.position_executor import PositionExecutor
from hummingbot.smart_components.models.executor_actions import (
    CreateExecutorAction,
    ExecutorAction,
    StopExecutorAction,
    StoreExecutorAction,
)
from hummingbot.smart_components.models.executors_info import ExecutorHandlerInfo, ExecutorInfo
from hummingbot.smart_components.strategy_frameworks.executor_handler_base import ExecutorHandlerBase
from hummingbot.smart_components.strategy_frameworks.generic_strategy.generic_controller import GenericController
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class GenericExecutorHandler(ExecutorHandlerBase):
    """
    Generic executor handler for a strategy.
    """
    def __init__(self, strategy: ScriptStrategyBase, controller: GenericController, update_interval: float = 1.0,
                 executors_update_interval: float = 1.0):
        super().__init__(strategy, controller, update_interval, executors_update_interval)
        self.controller = controller
        self.position_executors = []
        self.dca_executors = []
        self.arbitrage_executors = []
        self.stored_executors_ids = set()

    def on_start(self):
        super().on_start()
        if self.controller.is_perpetual:
            self.set_leverage_and_position_mode()

    def on_stop(self):
        """Actions to perform on stop."""
        super().on_stop()

    def stop(self):
        """Stop the executor handler."""
        super().stop()
        self.stop_all_executors()

    def stop_all_executors(self):
        for executor in self.position_executors + self.dca_executors + self.arbitrage_executors:
            executor.early_stop()

    async def control_task(self):
        """
        Override the control task to implement the dynamic behavior.
        """
        # Collect data for active executors
        executor_handler_report: ExecutorHandlerInfo = self.get_executor_handler_report()

        # Determine actions based on the collected data
        await self.controller.update_executor_handler_report(executor_handler_report)
        actions: Optional[List[ExecutorAction]] = await self.controller.determine_actions()

        # Execute actions
        await self.execute_actions(actions)

    def get_active_position_executors(self) -> List[ExecutorInfo]:
        """
        Get the active position executors.
        """
        return [executor.executor_info for executor in self.position_executors if not executor.is_closed]

    def get_closed_position_executors(self) -> List[ExecutorInfo]:
        """
        Get the closed position executors.
        """
        return [executor.executor_info for executor in self.position_executors if executor.is_closed]

    def get_active_dca_executors(self) -> List[ExecutorInfo]:
        """
        Get the active DCA executors.
        """
        return [executor.executor_info for executor in self.dca_executors if not executor.is_closed]

    def get_closed_dca_executors(self) -> List[ExecutorInfo]:
        """
        Get the closed DCA executors.
        """
        return [executor.executor_info for executor in self.dca_executors if executor.is_closed]

    def get_active_arbitrage_executors(self) -> List[ExecutorInfo]:
        """
        Get the active arbitrage executors.
        """
        return [executor.executor_info for executor in self.arbitrage_executors if not executor.is_closed]

    def get_closed_arbitrage_executors(self) -> List[ExecutorInfo]:
        """
        Get the closed arbitrage executors.
        """
        return [executor.executor_info for executor in self.arbitrage_executors if executor.is_closed]

    def get_executor_handler_report(self):
        """
        Compute information about executors.
        """
        executor_handler_report = ExecutorHandlerInfo(
            controller_id=self.controller.config.id,  # TODO: placeholder to refactor using async.Queue to communicate with the controller
            timestamp=time.time(),
            status=self.status,
            active_position_executors=self.get_active_position_executors(),
            closed_position_executors=self.get_closed_position_executors(),
            active_dca_executors=self.get_active_dca_executors(),
            closed_dca_executors=self.get_closed_dca_executors(),
            active_arbitrage_executors=self.get_active_arbitrage_executors(),
            closed_arbitrage_executors=self.get_closed_arbitrage_executors(),
        )
        return executor_handler_report

    async def execute_actions(self, actions: List[ExecutorAction]):
        """
        Execute the actions and return the status for each action.
        """
        for action in actions:
            if isinstance(action, CreateExecutorAction):
                # TODO:
                #  - evaluate if the id is unique
                #  - refactor to store the executor by controller id
                self.create_executor(action.executor_config)
            elif isinstance(action, StopExecutorAction):
                executor = self.get_executor_by_id(action.executor_id)
                if executor and executor.is_active:
                    executor.early_stop()
            elif isinstance(action, StoreExecutorAction):
                executor = self.get_executor_by_id(action.executor_id)
                if executor and executor.is_closed:
                    MarketsRecorder.get_instance().store_or_update_executor(executor)
                    self.remove_executor(executor)
                    self.stored_executors_ids.add(executor.config.id)
            else:
                raise ValueError(f"Unknown action type {type(action)}")

    def create_executor(self, executor_config):
        """
        Create an executor.
        """
        # TODO: refactor to use a factory
        if isinstance(executor_config, PositionExecutorConfig):
            executor = PositionExecutor(self.strategy, executor_config, self.executors_update_interval)
            executor.start()
            self.position_executors.append(executor)
            self.logger().debug(f"Created position executor {executor_config.id}")
        elif isinstance(executor_config, DCAExecutorConfig):
            executor = DCAExecutor(self.strategy, executor_config, self.executors_update_interval)
            executor.start()
            self.dca_executors.append(executor)
            self.logger().debug(f"Created DCA executor {executor_config.id}")
        elif isinstance(executor_config, ArbitrageExecutorConfig):
            executor = ArbitrageExecutor(self.strategy, executor_config, self.executors_update_interval)
            executor.start()
            self.arbitrage_executors.append(executor)
            self.logger().debug(f"Created arbitrage executor {executor_config.id}")

    def get_executor_by_id(self, executor_id: str):
        """
        Get the executor by id.
        """
        all_executors = self.position_executors + self.dca_executors + self.arbitrage_executors
        executor = next((executor for executor in all_executors if executor.config.id == executor_id), None)
        return executor

    def remove_executor(self, executor: Union[PositionExecutor, DCAExecutor, ArbitrageExecutor]):
        """
        Remove the executor by id.
        """
        if isinstance(executor, PositionExecutor):
            self.position_executors.remove(executor)
        elif isinstance(executor, DCAExecutor):
            self.dca_executors.remove(executor)
        elif isinstance(executor, ArbitrageExecutor):
            self.arbitrage_executors.remove(executor)

    def set_leverage_and_position_mode(self):
        connector = self.strategy.connectors[self.controller.config.exchange]
        connector.set_position_mode(self.controller.config.position_mode)
        connector.set_leverage(trading_pair=self.controller.config.trading_pair, leverage=self.controller.config.leverage)

    def get_active_executors_performance_report(self):
        """
        Get the performance report for active executors.
        """
        all_executors = self.position_executors + self.dca_executors + self.arbitrage_executors
        net_pnl_pct = sum([executor.net_pnl_pct for executor in all_executors])
        net_pnl_quote = sum([executor.net_pnl_quote for executor in all_executors])
        volume_traded = sum([executor.filled_amount_quote for executor in all_executors])
        return net_pnl_pct, net_pnl_quote, volume_traded

    def get_stored_executors_performance_report(self):
        """
        Get the performance report for stored executors.
        """
        all_executors = MarketsRecorder.get_instance().get_executors_by_ids(list(self.stored_executors_ids))
        net_pnl_pct = sum([executor.net_pnl_pct for executor in all_executors])
        net_pnl_quote = sum([executor.net_pnl_quote for executor in all_executors])
        volume_traded = sum([executor.filled_amount_quote * 2 for executor in all_executors])
        return net_pnl_pct, net_pnl_quote, volume_traded

    def to_format_status(self) -> str:
        """
        Base status for executor handler.
        """
        lines = []
        lines.extend(self.controller.to_format_status())
        lines.append("\nActive executors performance report:")
        net_pnl_pct, net_pnl_quote, volume_traded = self.get_active_executors_performance_report()
        lines.append(f"Net PnL %: {net_pnl_pct:.2f} | Net PnL Quote: {net_pnl_quote:.2f} | Volume Traded: {volume_traded:.2f}\n")
        lines.append("Stored executors performance report:")
        net_pnl_pct, net_pnl_quote, volume_traded = self.get_stored_executors_performance_report()
        lines.append(f"Net PnL %: {net_pnl_pct:.2f} | Net PnL Quote: {net_pnl_quote:.2f} | Volume Traded: {volume_traded:.2f}\n")
        return "\n".join(lines)
