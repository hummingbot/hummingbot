import logging
from collections import Counter
from decimal import Decimal
from typing import Dict, List

from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.logger import HummingbotLogger
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
from hummingbot.smart_components.models.executors_info import ExecutorInfo, PerformanceReport
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class ExecutorOrchestrator:
    """
    Orchestrator for various executors.
    """
    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, strategy: ScriptStrategyBase, executors_update_interval: float = 1.0):
        self.strategy = strategy
        self.executors_update_interval = executors_update_interval
        self.executors = {}

    def stop(self):
        """
        Stop the orchestrator task and all active executors.
        """
        # first we stop all active executors
        for controller_id, executors_list in self.executors.items():
            for executor in executors_list:
                executor.early_stop()
        # then we store all executors
        for controller_id, executors_list in self.executors.items():
            for executor in executors_list:
                MarketsRecorder.get_instance().store_or_update_executor(executor)

    def execute_action(self, action: ExecutorAction):
        """
        Execute the action and handle executors based on action type.
        """
        controller_id = action.controller_id
        if controller_id not in self.executors:
            self.executors[controller_id] = []

        if isinstance(action, CreateExecutorAction):
            self.create_executor(action)
        elif isinstance(action, StopExecutorAction):
            self.stop_executor(action)
        elif isinstance(action, StoreExecutorAction):
            self.store_executor(action)

    def execute_actions(self, actions: List[ExecutorAction]):
        """
        Execute a list of actions.
        """
        for action in actions:
            self.execute_action(action)

    def create_executor(self, action: CreateExecutorAction):
        """
        Create an executor based on the configuration in the action.
        """
        controller_id = action.controller_id
        executor_config = action.executor_config

        # For now, we replace the controller ID in the executor config with the actual controller object to mantain
        # compa
        executor_config.controller_id = controller_id

        if isinstance(executor_config, PositionExecutorConfig):
            executor = PositionExecutor(self.strategy, executor_config, self.executors_update_interval)
        elif isinstance(executor_config, DCAExecutorConfig):
            executor = DCAExecutor(self.strategy, executor_config, self.executors_update_interval)
        elif isinstance(executor_config, ArbitrageExecutorConfig):
            executor = ArbitrageExecutor(self.strategy, executor_config, self.executors_update_interval)
        else:
            raise ValueError("Unsupported executor config type")

        executor.start()
        self.executors[controller_id].append(executor)
        self.logger().debug(f"Created {type(executor).__name__} for controller {controller_id}")

    def stop_executor(self, action: StopExecutorAction):
        """
        Stop an executor based on the action details.
        """
        controller_id = action.controller_id
        executor_id = action.executor_id

        executor = next((executor for executor in self.executors[controller_id] if executor.config.id == executor_id), None)
        if not executor:
            self.logger().error(f"Executor ID {executor_id} not found for controller {controller_id}.")
            return
        executor.early_stop()

    def store_executor(self, action: StoreExecutorAction):
        """
        Store executor data based on the action details.
        """
        controller_id = action.controller_id
        executor_id = action.executor_id

        executor = next((executor for executor in self.executors[controller_id] if executor.config.id == executor_id), None)
        if not executor:
            self.logger().error(f"Executor ID {executor_id} not found for controller {controller_id}.")
            return
        if executor.is_active:
            self.logger().error(f"Executor ID {executor_id} is still active.")
            return
        MarketsRecorder.get_instance().store_or_update_executor(executor)
        self.executors[controller_id].remove(executor)

    def get_executors_report(self) -> Dict[str, List[ExecutorInfo]]:
        """
        Generate a report of all executors.
        """
        report = {}
        for controller_id, executors_list in self.executors.items():
            report[controller_id] = [executor.executor_info for executor in executors_list if executor]
        return report

    def generate_performance_report(self, controller_id: str) -> PerformanceReport:
        # Fetch executors from database and active in-memory executors
        db_executors = MarketsRecorder.get_instance().get_executors_by_controller(controller_id)
        active_executor_ids = [executor.executor_info.id for executor in self.executors.get(controller_id, [])]
        filtered_db_executors = [executor for executor in db_executors if executor.id not in active_executor_ids]
        combined_executors = self.executors.get(controller_id, []) + filtered_db_executors

        # Initialize performance metrics
        realized_pnl_quote = Decimal(0)
        unrealized_pnl_quote = Decimal(0)
        volume_traded = Decimal(0)
        close_type_counts = Counter()

        for executor in combined_executors:
            if executor.is_active:  # For active executors
                unrealized_pnl_quote += executor.net_pnl_quote
            else:  # For closed executors
                realized_pnl_quote += executor.net_pnl_quote
                close_type_counts[executor.close_type] += 1
            volume_traded += executor.filled_amount_quote

        # Calculate global PNL values
        global_pnl_quote = unrealized_pnl_quote + realized_pnl_quote
        global_pnl_pct = (global_pnl_quote / volume_traded) * 100 if volume_traded != 0 else Decimal(0)

        # Calculate individual PNL percentages
        unrealized_pnl_pct = (unrealized_pnl_quote / volume_traded) * 100 if volume_traded != 0 else Decimal(0)
        realized_pnl_pct = (realized_pnl_quote / volume_traded) * 100 if volume_traded != 0 else Decimal(0)

        # Create Performance Report
        report = PerformanceReport(
            realized_pnl_quote=realized_pnl_quote,
            unrealized_pnl_quote=unrealized_pnl_quote,
            unrealized_pnl_pct=unrealized_pnl_pct,
            realized_pnl_pct=realized_pnl_pct,
            global_pnl_quote=global_pnl_quote,
            global_pnl_pct=global_pnl_pct,
            volume_traded=volume_traded,
            close_type_counts=close_type_counts
        )

        return report
