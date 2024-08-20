import logging
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
from hummingbot.strategy_v2.models.executors import CloseType
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
        self.executors = {}

    def stop(self):
        """
        Stop the orchestrator task and all active executors.
        """
        # first we stop all active executors
        for controller_id, executors_list in self.executors.items():
            for executor in executors_list:
                if not executor.is_closed:
                    executor.early_stop()

    def store_all_executors(self):
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
        elif isinstance(executor_config, TWAPExecutorConfig):
            executor = TWAPExecutor(self.strategy, executor_config, self.executors_update_interval)
        elif isinstance(executor_config, XEMMExecutorConfig):
            executor = XEMMExecutor(self.strategy, executor_config, self.executors_update_interval)
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

        executor = next((executor for executor in self.executors[controller_id] if executor.config.id == executor_id),
                        None)
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

        executor = next((executor for executor in self.executors[controller_id] if executor.config.id == executor_id),
                        None)
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
        active_executors = [executor.executor_info for executor in self.executors.get(controller_id, [])]
        combined_executors = active_executors + filtered_db_executors

        # Initialize performance metrics
        realized_pnl_quote = Decimal(0)
        unrealized_pnl_quote = Decimal(0)
        volume_traded = Decimal(0)
        open_order_volume = Decimal(0)
        inventory_imbalance = Decimal(0)
        close_type_counts = {}

        for executor in combined_executors:
            close_type = executor.close_type
            if close_type == CloseType.FAILED:
                close_type_counts[close_type] = close_type_counts.get(close_type, 0) + 1
                continue
            elif close_type is not None:
                if close_type in close_type_counts:
                    close_type_counts[close_type] += 1
                else:
                    close_type_counts[close_type] = 1
            if executor.is_active:  # For active executors
                unrealized_pnl_quote += executor.net_pnl_quote
                side = executor.custom_info.get("side", None)
                if side:
                    inventory_imbalance += executor.filled_amount_quote if side == TradeType.BUY else -executor.filled_amount_quote
                if executor.type == "dca_executor":
                    open_order_volume += sum(executor.config.amounts_quote) - executor.filled_amount_quote
                elif executor.type == "position_executor":
                    open_order_volume += (executor.config.amount * executor.config.entry_price) - executor.filled_amount_quote
            else:  # For closed executors
                realized_pnl_quote += executor.net_pnl_quote
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
            open_order_volume=open_order_volume,
            inventory_imbalance=inventory_imbalance,
            close_type_counts=close_type_counts
        )

        return report

    def generate_global_performance_report(self) -> PerformanceReport:
        global_realized_pnl_quote = Decimal(0)
        global_unrealized_pnl_quote = Decimal(0)
        global_volume_traded = Decimal(0)
        global_open_order_volume = Decimal(0)
        global_inventory_imbalance = Decimal(0)
        global_close_type_counts = {}

        for controller_id in self.executors.keys():
            report = self.generate_performance_report(controller_id)
            global_realized_pnl_quote += report.realized_pnl_quote
            global_unrealized_pnl_quote += report.unrealized_pnl_quote
            global_volume_traded += report.volume_traded
            global_open_order_volume += report.open_order_volume
            global_inventory_imbalance += report.inventory_imbalance

            for close_type, count in report.close_type_counts.items():
                global_close_type_counts[close_type] = global_close_type_counts.get(close_type, 0) + count

        global_pnl_quote = global_realized_pnl_quote + global_unrealized_pnl_quote
        global_pnl_pct = (global_pnl_quote / global_volume_traded) * 100 if global_volume_traded != 0 else Decimal(0)

        return PerformanceReport(
            realized_pnl_quote=global_realized_pnl_quote,
            unrealized_pnl_quote=global_unrealized_pnl_quote,
            realized_pnl_pct=(global_realized_pnl_quote / global_volume_traded) * 100 if global_volume_traded != 0 else Decimal(0),
            unrealized_pnl_pct=(global_unrealized_pnl_quote / global_volume_traded) * 100 if global_volume_traded != 0 else Decimal(0),
            global_pnl_quote=global_pnl_quote,
            global_pnl_pct=global_pnl_pct,
            volume_traded=global_volume_traded,
            open_order_volume=global_open_order_volume,
            inventory_imbalance=global_inventory_imbalance,
            close_type_counts=global_close_type_counts
        )
