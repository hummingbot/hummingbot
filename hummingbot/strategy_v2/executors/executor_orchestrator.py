import logging
from copy import deepcopy
from decimal import Decimal
from typing import Dict, List

from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.core.data_type.common import TradeType
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.arbitrage_executor.arbitrage_executor import ArbitrageExecutor
from hummingbot.strategy_v2.executors.arbitrage_executor.data_types import ArbitrageExecutorConfig
from hummingbot.strategy_v2.executors.dca_executor.data_types import DCAExecutorConfig
from hummingbot.strategy_v2.executors.dca_executor.dca_executor import DCAExecutor
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.strategy_v2.executors.position_executor.position_executor import PositionExecutor
from hummingbot.strategy_v2.executors.twap_executor.data_types import TWAPExecutorConfig
from hummingbot.strategy_v2.executors.twap_executor.twap_executor import TWAPExecutor
from hummingbot.strategy_v2.executors.xemm_executor.data_types import XEMMExecutorConfig
from hummingbot.strategy_v2.executors.xemm_executor.xemm_executor import XEMMExecutor
from hummingbot.strategy_v2.models.executor_actions import (
    CreateExecutorAction,
    ExecutorAction,
    StopExecutorAction,
    StoreExecutorAction,
)
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo, PerformanceReport


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
        self.active_executors = {}
        self.archived_executors = {}
        self.cached_performance = {}
        self._initialize_cached_performance()

    def _initialize_cached_performance(self):
        """
        Initialize cached performance by querying the database for stored executors.
        """
        db_executors = MarketsRecorder.get_instance().get_all_executors()
        for executor in db_executors:
            controller_id = executor.controller_id
            if controller_id not in self.cached_performance:
                self.cached_performance[controller_id] = PerformanceReport()
            self._update_cached_performance(controller_id, executor)

    def _update_cached_performance(self, controller_id: str, executor_info: ExecutorInfo):
        """
        Update the cached performance for a specific controller with an executor's information.
        """
        report = self.cached_performance[controller_id]
        report.realized_pnl_quote += executor_info.net_pnl_quote
        report.volume_traded += executor_info.filled_amount_quote
        if executor_info.close_type:
            report.close_type_counts[executor_info.close_type] = report.close_type_counts.get(executor_info.close_type, 0) + 1

    def stop(self):
        """
        Stop the orchestrator task and all active executors.
        """
        # first we stop all active executors
        for controller_id, executors_list in self.active_executors.items():
            for executor in executors_list:
                if not executor.is_closed:
                    executor.early_stop()

    def store_all_executors(self):
        for controller_id, executors_list in self.active_executors.items():
            for executor in executors_list:
                MarketsRecorder.get_instance().store_or_update_executor(executor)

    def execute_action(self, action: ExecutorAction):
        """
        Execute the action and handle executors based on action type.
        """
        controller_id = action.controller_id
        if controller_id not in self.active_executors:
            self.active_executors[controller_id] = []
            self.archived_executors[controller_id] = []
            self.cached_performance[controller_id] = PerformanceReport()

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
        elif isinstance(executor_config, TWAPExecutorConfig):
            executor = TWAPExecutor(self.strategy, executor_config, self.executors_update_interval)
        elif isinstance(executor_config, XEMMExecutorConfig):
            executor = XEMMExecutor(self.strategy, executor_config, self.executors_update_interval)
        else:
            raise ValueError("Unsupported executor config type")

        executor.start()
        self.active_executors[controller_id].append(executor)
        self.logger().debug(f"Created {type(executor).__name__} for controller {controller_id}")

    def stop_executor(self, action: StopExecutorAction):
        """
        Stop an executor based on the action details.
        """
        controller_id = action.controller_id
        executor_id = action.executor_id

        executor = next((executor for executor in self.active_executors[controller_id] if executor.config.id == executor_id),
                        None)
        if not executor:
            self.logger().error(f"Executor ID {executor_id} not found for controller {controller_id}.")
            return
        executor.early_stop()

    def store_executor(self, action: StoreExecutorAction):
        """
        Store executor data based on the action details and update cached performance.
        """
        controller_id = action.controller_id
        executor_id = action.executor_id

        executor = next((executor for executor in self.active_executors[controller_id] if executor.config.id == executor_id),
                        None)
        if not executor:
            self.logger().error(f"Executor ID {executor_id} not found for controller {controller_id}.")
            return
        if executor.is_active:
            self.logger().error(f"Executor ID {executor_id} is still active.")
            return
        MarketsRecorder.get_instance().store_or_update_executor(executor)
        self._update_cached_performance(controller_id, executor.executor_info)
        self.active_executors[controller_id].remove(executor)
        self.archived_executors[controller_id].append(executor.executor_info)
        del executor

    def get_executors_report(self) -> Dict[str, List[ExecutorInfo]]:
        """
        Generate a report of all executors.
        """
        report = {}
        for controller_id, executors_list in self.active_executors.items():
            report[controller_id] = [executor.executor_info for executor in executors_list if executor]
        return report

    def generate_performance_report(self, controller_id: str) -> PerformanceReport:
        # Start with a deep copy of the cached performance for this controller
        report = deepcopy(self.cached_performance.get(controller_id, PerformanceReport()))

        # Add data from active executors
        active_executors = self.active_executors.get(controller_id, [])
        for executor in active_executors:
            executor_info = executor.executor_info
            if executor_info.is_active:
                report.unrealized_pnl_quote += executor_info.net_pnl_quote
            else:
                report.realized_pnl_quote += executor_info.net_pnl_quote
            report.volume_traded += executor_info.filled_amount_quote
            side = executor_info.custom_info.get("side", None)
            if side:
                report.inventory_imbalance += executor_info.filled_amount_quote if side == TradeType.BUY else -executor_info.filled_amount_quote
            if executor_info.type == "dca_executor":
                report.open_order_volume += sum(executor_info.config.amounts_quote) - executor_info.filled_amount_quote
            elif executor_info.type == "position_executor":
                report.open_order_volume += (executor_info.config.amount * executor_info.config.entry_price) - executor_info.filled_amount_quote

        # Calculate global PNL values
        report.global_pnl_quote = report.unrealized_pnl_quote + report.realized_pnl_quote
        report.global_pnl_pct = (report.global_pnl_quote / report.volume_traded) * 100 if report.volume_traded != 0 else Decimal(0)

        # Calculate individual PNL percentages
        report.unrealized_pnl_pct = (report.unrealized_pnl_quote / report.volume_traded) * 100 if report.volume_traded != 0 else Decimal(0)
        report.realized_pnl_pct = (report.realized_pnl_quote / report.volume_traded) * 100 if report.volume_traded != 0 else Decimal(0)

        return report

    def generate_global_performance_report(self) -> PerformanceReport:
        global_report = PerformanceReport()

        for controller_id in set(list(self.active_executors.keys()) + list(self.cached_performance.keys())):
            report = self.generate_performance_report(controller_id)
            global_report.realized_pnl_quote += report.realized_pnl_quote
            global_report.unrealized_pnl_quote += report.unrealized_pnl_quote
            global_report.volume_traded += report.volume_traded
            global_report.open_order_volume += report.open_order_volume
            global_report.inventory_imbalance += report.inventory_imbalance

            for close_type, count in report.close_type_counts.items():
                global_report.close_type_counts[close_type] = global_report.close_type_counts.get(close_type, 0) + count

        global_report.global_pnl_quote = global_report.realized_pnl_quote + global_report.unrealized_pnl_quote
        global_report.global_pnl_pct = (global_report.global_pnl_quote / global_report.volume_traded) * 100 if global_report.volume_traded != 0 else Decimal(0)
        global_report.realized_pnl_pct = (global_report.realized_pnl_quote / global_report.volume_traded) * 100 if global_report.volume_traded != 0 else Decimal(0)
        global_report.unrealized_pnl_pct = (global_report.unrealized_pnl_quote / global_report.volume_traded) * 100 if global_report.volume_traded != 0 else Decimal(0)

        return global_report
