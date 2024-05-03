from decimal import Decimal
from typing import List

import numpy as np
import pandas as pd

from hummingbot.core.data_type.common import TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.backtesting.backtesting_data_provider import BacktestingDataProvider
from hummingbot.strategy_v2.backtesting.executor_simulator_base import ExecutorSimulation
from hummingbot.strategy_v2.backtesting.executors_simulator.position_executor_simulator import PositionExecutorSimulator
from hummingbot.strategy_v2.controllers.controller_base import ControllerConfigBase
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, StopExecutorAction
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class BacktestingEngineBase:
    def __init__(self):
        self.controller = None
        self.backtesting_resolution = None
        self.position_executor_simulator = PositionExecutorSimulator()

    async def run_backtesting(self,
                              controller_config: ControllerConfigBase,
                              start: int, end: int,
                              backtesting_resolution: str = "1m",
                              trade_cost=0.0006):
        # Load historical candles
        controller_class = controller_config.get_controller_class()
        backtesting_data_provider = BacktestingDataProvider(connectors={}, start_time=start, end_time=end)
        self.controller = controller_class(config=controller_config, market_data_provider=backtesting_data_provider,
                                           actions_queue=None)
        self.backtesting_resolution = backtesting_resolution
        await self.initialize_backtesting_data_provider()
        await self.controller.update_processed_data()
        executors_info = self.simulate_execution(trade_cost=trade_cost)
        results = self.summarize_results(executors_info)
        return {
            "executors": executors_info,
            "results": results,
            "processed_data": self.controller.processed_data,
        }

    async def initialize_backtesting_data_provider(self):
        backtesting_config = CandlesConfig(
            connector=self.controller.config.connector_name,
            trading_pair=self.controller.config.trading_pair,
            interval=self.backtesting_resolution
        )
        await self.controller.market_data_provider.initialize_candles_feed(backtesting_config)
        for config in self.controller.config.candles_config:
            await self.controller.market_data_provider.initialize_candles_feed(config)

    def simulate_execution(self, trade_cost: float) -> list:
        """
        Simulates market making strategy over historical data, considering trading costs.

        Args:
            trade_cost (float): The cost per trade.

        Returns:
            List[ExecutorInfo]: List of executor information objects detailing the simulation results.
        """
        processed_features = self.prepare_market_data()
        self.active_executor_simulations: List[ExecutorSimulation] = []
        self.stopped_executors_info: List[ExecutorInfo] = []

        for i, row in processed_features.iterrows():
            self.update_market_data(row)
            self.update_processed_data(row)
            self.update_executors_info(row["timestamp"])
            for action in self.controller.determine_executor_actions():
                config = action.executor_config
                if isinstance(action, CreateExecutorAction) and isinstance(config, PositionExecutorConfig):
                    executor_simulation = self.position_executor_simulator.simulate(
                        df=processed_features.loc[i:],
                        config=config,
                        trade_cost=trade_cost)
                    self.manage_active_executors(executor_simulation)
                elif isinstance(action, StopExecutorAction):
                    self.handle_stop_action(action, row["timestamp"])

        return self.controller.executors_info

    def update_executors_info(self, timestamp: pd.Timestamp):
        active_executors_info = []
        for executor in self.active_executor_simulations:
            executor_info = executor.get_executor_info_at_timestamp(timestamp)
            if executor_info.status == RunnableStatus.TERMINATED:
                self.stopped_executors_info.append(executor_info)
                self.active_executor_simulations.remove(executor)
            else:
                active_executors_info.append(executor_info)
        self.controller.executors_info = active_executors_info + self.stopped_executors_info

    def update_processed_data(self, row: pd.Series):
        """
        Updates processed data in the controller with the current price and timestamp.

        Args:
            row (pd.Series): The current row of market data.
        """
        raise NotImplementedError("update_processed_data method must be implemented in a subclass.")

    def prepare_market_data(self) -> pd.DataFrame:
        """
        Prepares market data by merging candle data with strategy features, filling missing values.

        Returns:
            pd.DataFrame: The prepared market data with necessary features.
        """
        backtesting_candles = self.controller.market_data_provider.get_candles_df(
            connector_name=self.controller.config.connector_name,
            trading_pair=self.controller.config.trading_pair,
            interval=self.backtesting_resolution
        )
        if "features" not in self.controller.processed_data:
            backtesting_candles["reference_price"] = backtesting_candles["close"]
            backtesting_candles["spread_multiplier"] = 1
            backtesting_candles["signal"] = 0
        else:
            backtesting_candles = backtesting_candles.merge_asof(self.controller.processed_data["features"],
                                                                 on="timestamp", direction="backward")

        self.controller.processed_data["features"] = backtesting_candles
        return backtesting_candles

    def update_market_data(self, row: pd.Series):
        """
        Updates market data in the controller with the current price and timestamp.

        Args:
            row (pd.Series): The current row of market data.
        """
        connector_name = self.controller.config.connector_name
        trading_pair = self.controller.config.trading_pair
        self.controller.market_data_provider.prices = {f"{connector_name}_{trading_pair}": Decimal(row["close"])}
        self.controller.market_data_provider._time = row["timestamp"]

    def simulate_executor(self, config: PositionExecutorConfig, df: pd.DataFrame,
                          trade_cost: Decimal) -> ExecutorSimulation:
        """
        Simulates the execution of a trading strategy given a configuration.

        Args:
            config (PositionExecutorConfig): The configuration of the executor.
            df (pd.DataFrame): DataFrame containing the market data from the start time.
            trade_cost (Decimal): The cost per trade.

        Returns:
            ExecutorSimulation: The results of the simulation.
        """
        return self.position_executor_simulator.simulate(df, config, trade_cost)

    def manage_active_executors(self, simulation: ExecutorSimulation):
        """
        Manages the list of active executors based on the simulation results.

        Args:
            simulation (ExecutorSimulation): The simulation results of the current executor.
            active_executors (list): The list of active executors.
        """
        if not simulation.executor_simulation.empty:
            self.active_executor_simulations.append(simulation)

    def handle_stop_action(self, action: StopExecutorAction, timestamp: pd.Timestamp):
        """
        Handles stop actions for executors, terminating them as required.

        Args:
            action (StopExecutorAction): The action indicating which executor to stop.
            active_executors (list): The list of active executors.
            timestamp (pd.Timestamp): The current timestamp.
        """
        for executor in self.active_executor_simulations:
            executor_info = executor.get_executor_info_at_timestamp(timestamp)
            if executor_info.config.id == action.executor_id:
                executor_info.status = RunnableStatus.TERMINATED
                executor_info.close_timestamp = timestamp
                self.stopped_executors_info.append(executor_info)
                self.active_executor_simulations.remove(executor)

    @staticmethod
    def summarize_results(executors_info, total_amount_quote=1000):
        if len(executors_info) > 0:
            executors_df = pd.DataFrame([ei.to_dict() for ei in executors_info])
            net_pnl_quote = executors_df["net_pnl_quote"].sum()
            total_executors = executors_df.shape[0]
            executors_with_position = executors_df[executors_df["net_pnl_quote"] != 0]
            total_executors_with_position = executors_with_position.shape[0]
            total_volume = executors_with_position["filled_amount_quote"].sum() * 2
            total_long = (executors_with_position["side"] == TradeType.BUY).sum()
            total_short = (executors_with_position["side"] == TradeType.SELL).sum()
            correct_long = ((executors_with_position["side"] == TradeType.BUY) & (executors_with_position["net_pnl_quote"] > 0)).sum()
            correct_short = ((executors_with_position["side"] == TradeType.SELL) & (executors_with_position["net_pnl_quote"] > 0)).sum()
            accuracy_long = correct_long / total_long if total_long > 0 else 0
            accuracy_short = correct_short / total_short if total_short > 0 else 0
            executors_df["close_type_name"] = executors_df["close_type"].apply(lambda x: x.name)
            close_types = executors_df.groupby("close_type_name")["timestamp"].count()

            # Additional metrics
            total_positions = executors_df.shape[0]
            win_signals = executors_df[executors_df["net_pnl_quote"] > 0]
            loss_signals = executors_df[executors_df["net_pnl_quote"] < 0]
            accuracy = win_signals.shape[0] / total_positions
            cumulative_returns = executors_df["net_pnl_quote"].cumsum()
            executors_df["cumulative_returns"] = cumulative_returns
            executors_df["cumulative_volume"] = executors_df["filled_amount_quote"].cumsum()
            executors_df["inventory"] = total_amount_quote + cumulative_returns

            peak = np.maximum.accumulate(cumulative_returns)
            drawdown = (cumulative_returns - peak)
            max_draw_down = np.min(drawdown)
            max_drawdown_pct = max_draw_down / executors_df["inventory"].iloc[0]
            returns = pd.to_numeric(executors_df["cumulative_returns"] / executors_df["cumulative_volume"])
            sharpe_ratio = returns.mean() / returns.std()
            total_won = win_signals.loc[:, "net_pnl_quote"].sum()
            total_loss = - loss_signals.loc[:, "net_pnl_quote"].sum()
            profit_factor = total_won / total_loss if total_loss > 0 else 1
            net_pnl_pct = net_pnl_quote / total_amount_quote

            return {
                "net_pnl": net_pnl_pct,
                "net_pnl_quote": net_pnl_quote,
                "total_executors": total_executors,
                "total_executors_with_position": total_executors_with_position,
                "total_volume": total_volume,
                "total_long": total_long,
                "total_short": total_short,
                "close_types": close_types,
                "accuracy_long": accuracy_long,
                "accuracy_short": accuracy_short,
                "total_positions": total_positions,
                "accuracy": accuracy,
                "max_drawdown_usd": max_draw_down,
                "max_drawdown_pct": max_drawdown_pct,
                "sharpe_ratio": sharpe_ratio,
                "profit_factor": profit_factor,
                "win_signals": win_signals.shape[0],
                "loss_signals": loss_signals.shape[0],
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
            "total_positions": 0,
            "accuracy": 0,
            "max_drawdown_usd": 0,
            "max_drawdown_pct": 0,
            "sharpe_ratio": 0,
            "profit_factor": 0,
            "win_signals": 0,
            "loss_signals": 0,
        }
