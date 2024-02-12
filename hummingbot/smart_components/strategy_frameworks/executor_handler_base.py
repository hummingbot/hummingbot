import asyncio
import logging

import pandas as pd

from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionSide
from hummingbot.logger import HummingbotLogger
from hummingbot.model.position_executors import PositionExecutors
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.smart_components.executors.position_executor.position_executor import PositionExecutor
from hummingbot.smart_components.smart_component_base import SmartComponentBase
from hummingbot.smart_components.strategy_frameworks.controller_base import ControllerBase
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class ExecutorHandlerBase(SmartComponentBase):
    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, strategy: ScriptStrategyBase, controller: ControllerBase, update_interval: float = 1.0,
                 executors_update_interval: float = 1.0):
        """
        Initialize the ExecutorHandlerBase.

        :param strategy: The strategy instance.
        :param controller: The controller instance.
        :param update_interval: Update interval in seconds.
        """
        super().__init__(update_interval)
        self.strategy = strategy
        self.controller = controller
        self.update_interval = update_interval
        self.executors_update_interval = executors_update_interval
        self.terminated = asyncio.Event()
        self.position_executors = {}
        self.dca_executors = []

    def on_stop(self):
        """Actions to perform on stop."""
        self.controller.stop()

    def on_start(self):
        """Actions to perform on start."""
        self.controller.start()

    async def control_task(self):
        """Control task to be implemented by subclasses."""
        raise NotImplementedError

    def store_position_executor(self, level_id: str = None):
        """
        Store executor data to CSV.

        :param executor: The executor instance.
        :param level_id: The order level id.
        """
        executor = self.position_executors.get(level_id)
        if executor:
            executor_data = executor.to_json()
            executor_data["order_level"] = level_id
            executor_data["controller_name"] = self.controller.config.strategy_name
            MarketsRecorder.get_instance().store_position_executor(executor_data)
            self.position_executors[level_id] = None

    def create_position_executor(self, position_config: PositionExecutorConfig, level_id: str = None):
        """
        Create an executor.

        :param position_config: The position configuration.
        :param level_id: The order level id.
        """
        current_executor = self.position_executors.get(level_id)
        if current_executor:
            self.logger().warning(f"Executor for level {level_id} already exists.")
            return
        executor = PositionExecutor(self.strategy, position_config, update_interval=self.executors_update_interval)
        executor.start()
        self.position_executors[level_id] = executor

    def stop_position_executor(self, executor_id: str):
        """
        Stop an executor.

        :param executor_id: The executor ID.
        """
        executor = self.position_executors[executor_id]
        if executor:
            executor.early_stop()

    def close_open_positions(self, connector_name: str = None, trading_pair: str = None):
        """
        Close all open positions.

        :param connector_name: The connector name.
        :param trading_pair: The trading pair.
        """
        connector = self.strategy.connectors[connector_name]
        for pos_key, position in connector.account_positions.items():
            if position.trading_pair == trading_pair:
                action = self.strategy.sell if position.position_side == PositionSide.LONG else self.strategy.buy
                action(connector_name=connector_name,
                       trading_pair=position.trading_pair,
                       amount=abs(position.amount),
                       order_type=OrderType.MARKET,
                       price=connector.get_mid_price(position.trading_pair),
                       position_action=PositionAction.CLOSE)

    def get_closed_executors_df(self):
        executors = MarketsRecorder.get_instance().get_position_executors(
            self.controller.config.strategy_name,
            self.controller.config.exchange,
            self.controller.config.trading_pair)
        executors_df = PositionExecutors.to_pandas(executors)
        return executors_df

    def get_active_executors_df(self) -> pd.DataFrame:
        """
        Get active executors as a DataFrame.

        :return: DataFrame containing active executors.
        """
        executors_info = []
        for level, executor in self.position_executors.items():
            if executor:
                executor_info = executor.to_json()
                executor_info["level_id"] = level
                executors_info.append(executor_info)
        if len(executors_info) > 0:
            executors_df = pd.DataFrame(executors_info)
            executors_df.sort_values(by="entry_price", ascending=False, inplace=True)
            executors_df["spread_to_next_level"] = -1 * executors_df["entry_price"].pct_change(periods=1)
            return executors_df
        else:
            return pd.DataFrame()

    def get_dca_executors(self) -> list:
        """
        Get active dca executors as a DataFrame.
        """
        return [dca_executor.to_json() for dca_executor in self.dca_executors]

    @staticmethod
    def summarize_executors_df(executors_df):
        if len(executors_df) > 0:
            net_pnl = executors_df["net_pnl"].sum()
            net_pnl_quote = executors_df["net_pnl_quote"].sum()
            total_executors = executors_df.shape[0]
            executors_with_position = executors_df[executors_df["net_pnl"] != 0]
            total_executors_with_position = executors_with_position.shape[0]
            total_volume = executors_with_position["amount"].sum() * 2
            total_long = (executors_with_position["side"] == "BUY").sum()
            total_short = (executors_with_position["side"] == "SELL").sum()
            correct_long = ((executors_with_position["side"] == "BUY") & (executors_with_position["net_pnl"] > 0)).sum()
            correct_short = ((executors_with_position["side"] == "SELL") & (executors_with_position["net_pnl"] > 0)).sum()
            accuracy_long = correct_long / total_long if total_long > 0 else 0
            accuracy_short = correct_short / total_short if total_short > 0 else 0

            close_types = executors_df.groupby("close_type")["timestamp"].count()
            return {
                "net_pnl": net_pnl,
                "net_pnl_quote": net_pnl_quote,
                "total_executors": total_executors,
                "total_executors_with_position": total_executors_with_position,
                "total_volume": total_volume,
                "total_long": total_long,
                "total_short": total_short,
                "close_types": close_types,
                "accuracy_long": accuracy_long,
                "accuracy_short": accuracy_short,
            }
        return {
            "net_pnl": 0,
            "net_pnl_quote": 0,
            "total_executors": 0,
            "total_executors_with_position": 0,
            "total_volume": 0,
            "total_long": 0,
            "total_short": 0,
            "close_types": 0,
            "accuracy_long": 0,
            "accuracy_short": 0,
        }

    def closed_executors_info(self):
        closed_executors = self.get_closed_executors_df()
        return self.summarize_executors_df(closed_executors)

    def active_executors_info(self):
        active_executors = self.get_active_executors_df()
        return self.summarize_executors_df(active_executors)

    def to_format_status(self) -> str:
        """
        Base status for executor handler.
        """
        lines = []
        lines.extend(self.controller.to_format_status())
        lines.extend(["\n################################ Active Executors ################################"])
        executors_df = self.get_active_executors_df()
        if len(executors_df) > 0:
            executors_df["amount_quote"] = executors_df["amount"] * executors_df["entry_price"]
            columns_to_show = ["level_id", "side", "entry_price", "close_price", "spread_to_next_level", "net_pnl",
                               "net_pnl_quote", "amount", "amount_quote", "timestamp", "close_type", "executor_status"]
            executors_df_str = format_df_for_printout(executors_df[columns_to_show].round(decimals=3),
                                                      table_format="psql")
            lines.extend([executors_df_str])
        lines.extend(["\n################################## Performance ##################################"])
        closed_executors_info = self.closed_executors_info()
        active_executors_info = self.active_executors_info()
        unrealized_pnl = float(active_executors_info["net_pnl"])
        realized_pnl = closed_executors_info["net_pnl"]
        total_pnl = unrealized_pnl + realized_pnl
        total_volume = closed_executors_info["total_volume"] + float(active_executors_info["total_volume"])
        total_long = closed_executors_info["total_long"] + float(active_executors_info["total_long"])
        total_short = closed_executors_info["total_short"] + float(active_executors_info["total_short"])
        accuracy_long = closed_executors_info["accuracy_long"]
        accuracy_short = closed_executors_info["accuracy_short"]
        total_accuracy = (accuracy_long * total_long + accuracy_short * total_short) \
            / (total_long + total_short) if (total_long + total_short) > 0 else 0
        lines.extend([f"""
| Unrealized PNL: {unrealized_pnl * 100:.2f} % | Realized PNL: {realized_pnl * 100:.2f} % | Total PNL: {total_pnl * 100:.2f} % | Total Volume: {total_volume}
| Total positions: {total_short + total_long} --> Accuracy: {total_accuracy:.2%}
    | Long: {total_long} --> Accuracy: {accuracy_long:.2%} | Short: {total_short} --> Accuracy: {accuracy_short:.2%}

Closed executors: {closed_executors_info["total_executors"]}
    {closed_executors_info["close_types"]}
    """])
        return "\n".join(lines)

    async def _sleep(self, delay: float):
        """
        Method created to enable tests to prevent processes from sleeping
        """
        await asyncio.sleep(delay)
