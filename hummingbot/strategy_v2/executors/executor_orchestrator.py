import logging
import uuid
from copy import deepcopy
from decimal import Decimal
from typing import Dict, List

from pydantic.main import BaseModel

from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.core.data_type.common import PriceType, TradeType
from hummingbot.logger import HummingbotLogger
from hummingbot.model.position import Position
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.arbitrage_executor.arbitrage_executor import ArbitrageExecutor
from hummingbot.strategy_v2.executors.arbitrage_executor.data_types import ArbitrageExecutorConfig
from hummingbot.strategy_v2.executors.dca_executor.data_types import DCAExecutorConfig
from hummingbot.strategy_v2.executors.dca_executor.dca_executor import DCAExecutor
from hummingbot.strategy_v2.executors.grid_executor.data_types import GridExecutorConfig
from hummingbot.strategy_v2.executors.grid_executor.grid_executor import GridExecutor
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


class PositionSummary(BaseModel):
    connector_name: str
    trading_pair: str
    volume_traded_quote: Decimal
    amount: Decimal
    breakeven_price: Decimal
    unrealized_pnl_quote: Decimal
    cum_fees_quote: Decimal


class PositionHeld:
    def __init__(self, connector_name: str, trading_pair: str):
        self.connector_name = connector_name
        self.trading_pair = trading_pair
        self.filled_orders = []

    def add_orders_from_executor(self, executor: ExecutorInfo):
        custom_info = executor.custom_info
        if "held_position_orders" in custom_info:
            self.filled_orders.extend(custom_info["held_position_orders"])

    def get_position_summary(self, mid_price: Decimal):
        volume_traded_quote = Decimal("0")
        net_amount = Decimal("0")
        total_cost = Decimal("0")
        cum_fees_quote = Decimal("0")

        for order in self.filled_orders:
            executed_amount_base = Decimal(str(order.get("executed_amount_base", 0)))
            executed_amount_quote = Decimal(str(order.get("executed_amount_quote", 0)))
            is_buy = order.get("trade_type") == "BUY"

            # Calculate volume traded in quote
            volume_traded_quote += executed_amount_quote

            # Calculate net position amount (buy - sell) and total cost
            if is_buy:
                net_amount += executed_amount_base
                total_cost += executed_amount_quote
            else:
                net_amount -= executed_amount_base
                total_cost -= executed_amount_quote

            # Add fees in quote directly from the order
            cum_fees_quote += Decimal(str(order.get("cumulative_fee_paid_quote", 0)))

        # Calculate breakeven price
        breakeven_price = abs(total_cost / net_amount) if net_amount != 0 else Decimal("0")

        # Calculate unrealized PnL in quote
        unrealized_pnl = (mid_price - breakeven_price) * net_amount if net_amount != 0 else Decimal("0")

        return PositionSummary(
            connector_name=self.connector_name,
            trading_pair=self.trading_pair,
            volume_traded_quote=volume_traded_quote,
            amount=net_amount,
            breakeven_price=breakeven_price,
            unrealized_pnl_quote=unrealized_pnl,
            cum_fees_quote=cum_fees_quote)


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
        self.positions_held = {}
        self.executors_ids_position_held = []
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
                self.active_executors[controller_id] = []
                self.archived_executors[controller_id] = []
                self.positions_held[controller_id] = []
            self._update_cached_performance(controller_id, executor)

    def _update_cached_performance(self, controller_id: str, executor_info: ExecutorInfo):
        """
        Update the cached performance for a specific controller with an executor's information.
        """
        report = self.cached_performance[controller_id]
        report.realized_pnl_quote += executor_info.net_pnl_quote
        report.volume_traded += executor_info.filled_amount_quote
        if executor_info.close_type:
            report.close_type_counts[executor_info.close_type] = report.close_type_counts.get(executor_info.close_type,
                                                                                              0) + 1

    def stop(self):
        """
        Stop the orchestrator task and all active executors.
        """
        # first we stop all active executors
        for controller_id, executors_list in self.active_executors.items():
            for executor in executors_list:
                if not executor.is_closed:
                    executor.early_stop()
        # Store all positions
        self.store_all_positions()

    def store_all_positions(self):
        """
        Store all positions in the database.
        """
        markets_recorder = MarketsRecorder.get_instance()
        for controller_id, positions_list in self.positions_held.items():
            for position in positions_list:
                mid_price = self.strategy.market_data_provider.get_price_by_type(
                    position.connector_name, position.trading_pair, PriceType.MidPrice)
                position_summary = position.get_position_summary(mid_price)

                # Create a new Position record
                position_record = Position(
                    id=str(uuid.uuid4()),
                    controller_id=controller_id,
                    connector_name=position_summary.connector_name,
                    trading_pair=position_summary.trading_pair,
                    timestamp=int(self.strategy.current_timestamp * 1e3),
                    volume_traded_quote=position_summary.volume_traded_quote,
                    amount=position_summary.amount,
                    breakeven_price=position_summary.breakeven_price,
                    unrealized_pnl_quote=position_summary.unrealized_pnl_quote,
                    cum_fees_quote=position_summary.cum_fees_quote,
                    filled_orders=position.filled_orders
                )
                # Store the position in the database
                markets_recorder.store_position(position_record)
                # Remove the position from the list
                self.positions_held[controller_id].remove(position)

    def store_all_executors(self):
        for controller_id, executors_list in self.active_executors.items():
            for executor in executors_list:
                # Store the executor in the database
                MarketsRecorder.get_instance().store_or_update_executor(executor)
                # Remove the executor from the list
                self.active_executors[controller_id].remove(executor)

    def execute_action(self, action: ExecutorAction):
        """
        Execute the action and handle executors based on action type.
        """
        controller_id = action.controller_id
        if controller_id not in self.cached_performance:
            self.active_executors[controller_id] = []
            self.archived_executors[controller_id] = []
            self.positions_held[controller_id] = []
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
        elif isinstance(executor_config, GridExecutorConfig):
            executor = GridExecutor(self.strategy, executor_config, self.executors_update_interval)
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
        # MarketsRecorder.get_instance().store_or_update_executor(executor)
        self.logger().debug(f"Created {type(executor).__name__} for controller {controller_id}")

    def stop_executor(self, action: StopExecutorAction):
        """
        Stop an executor based on the action details.
        """
        controller_id = action.controller_id
        executor_id = action.executor_id

        executor = next(
            (executor for executor in self.active_executors[controller_id] if executor.config.id == executor_id),
            None)
        if not executor:
            self.logger().error(f"Executor ID {executor_id} not found for controller {controller_id}.")
            return
        executor.early_stop(action.keep_position)

    def store_executor(self, action: StoreExecutorAction):
        """
        Store executor data based on the action details and update cached performance.
        """
        controller_id = action.controller_id
        executor_id = action.executor_id

        executor = next(
            (executor for executor in self.active_executors[controller_id] if executor.config.id == executor_id),
            None)
        if not executor:
            self.logger().error(f"Executor ID {executor_id} not found for controller {controller_id}.")
            return
        if executor.is_active:
            self.logger().error(f"Executor ID {executor_id} is still active.")
            return
        try:
            MarketsRecorder.get_instance().store_or_update_executor(executor)
            self._update_cached_performance(controller_id, executor.executor_info)
        except Exception as e:
            self.logger().error(f"Error storing executor id {executor_id}: {str(e)}.")
            self.logger().error(f"Executor info: {executor.executor_info} | Config: {executor.config}")

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

    def get_positions_report(self) -> Dict[str, List[PositionHeld]]:
        """
        Generate a report of all positions held.
        """
        report = {}
        for controller_id, positions_list in self.positions_held.items():
            positions_summary = []
            for position in positions_list:
                mid_price = self.strategy.market_data_provider.get_price_by_type(
                    position.connector_name, position.trading_pair, PriceType.MidPrice)
                positions_summary.append(position.get_position_summary(mid_price))
            report[controller_id] = positions_summary
        return report

    def generate_performance_report(self, controller_id: str) -> PerformanceReport:
        # Start with a deep copy of the cached performance for this controller
        report = deepcopy(self.cached_performance.get(controller_id, PerformanceReport()))

        # Add data from active executors
        active_executors = self.active_executors.get(controller_id, [])
        positions = self.positions_held.get(controller_id, [])
        for executor in active_executors:
            executor_info = executor.executor_info
            side = executor_info.custom_info.get("side", None)
            if executor_info.is_active:
                report.unrealized_pnl_quote += executor_info.net_pnl_quote
                if side:
                    report.inventory_imbalance += executor_info.filled_amount_quote \
                        if side == TradeType.BUY else -executor_info.filled_amount_quote
                if executor_info.type == "dca_executor":
                    report.open_order_volume += sum(
                        executor_info.config.amounts_quote) - executor_info.filled_amount_quote
                elif executor_info.type == "position_executor":
                    report.open_order_volume += (executor_info.config.amount *
                                                 executor_info.config.entry_price) - executor_info.filled_amount_quote
            else:
                report.realized_pnl_quote += executor_info.net_pnl_quote
                if executor_info.close_type in report.close_type_counts:
                    report.close_type_counts[executor_info.close_type] += 1
                else:
                    report.close_type_counts[executor_info.close_type] = 1
                if executor_info.close_type == CloseType.POSITION_HOLD and executor_info.config.id not in self.executors_ids_position_held:
                    self.executors_ids_position_held.append(executor_info.config.id)
                    position = next((position for position in positions if
                                     position.trading_pair == executor_info.trading_pair and position.connector_name == executor_info.connector_name),
                                    None)
                    if position:
                        position.add_orders_from_executor(executor_info)
                    else:
                        position = PositionHeld(executor_info.connector_name, executor_info.trading_pair)
                        position.add_orders_from_executor(executor_info)
                        positions.append(position)

            report.volume_traded += executor_info.filled_amount_quote

        # Add data from positions held

        for position in positions:
            mid_price = self.strategy.market_data_provider.get_price_by_type(
                position.connector_name, position.trading_pair, PriceType.MidPrice)
            position_summary = position.get_position_summary(mid_price)

            # Update report with position data
            report.volume_traded += position_summary.volume_traded_quote
            report.inventory_imbalance += position_summary.amount  # This is the net position amount
            report.unrealized_pnl_quote += position_summary.unrealized_pnl_quote - position_summary.cum_fees_quote

            # Store position summary in report for controller access
            if not hasattr(report, "positions_summary"):
                report.positions_summary = []
            report.positions_summary.append(position_summary)

        # Calculate global PNL values
        report.global_pnl_quote = report.unrealized_pnl_quote + report.realized_pnl_quote
        report.global_pnl_pct = (report.global_pnl_quote / report.volume_traded) * 100 if report.volume_traded != 0 else Decimal(0)

        # Calculate individual PNL percentages
        report.unrealized_pnl_pct = (report.unrealized_pnl_quote / report.volume_traded) * 100 if report.volume_traded != 0 else Decimal(0)
        report.realized_pnl_pct = (report.realized_pnl_quote / report.volume_traded) * 100 if report.volume_traded != 0 else Decimal(0)

        return report
