import importlib
import inspect
import os
from decimal import Decimal
from typing import Dict, List, Optional, Type, Union

import numpy as np
import pandas as pd
import yaml

from hummingbot.client import settings
from hummingbot.core.data_type.common import LazyDict, TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.exceptions import InvalidController
from hummingbot.strategy_v2.backtesting.backtesting_data_provider import BacktestingDataProvider
from hummingbot.strategy_v2.backtesting.executor_simulator_base import ExecutorSimulation
from hummingbot.strategy_v2.backtesting.executors_simulator.dca_executor_simulator import DCAExecutorSimulator
from hummingbot.strategy_v2.backtesting.executors_simulator.grid_executor_simulator import GridExecutorSimulator
from hummingbot.strategy_v2.backtesting.executors_simulator.order_executor_simulator import OrderExecutorSimulator
from hummingbot.strategy_v2.backtesting.executors_simulator.position_executor_simulator import PositionExecutorSimulator
from hummingbot.strategy_v2.controllers.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerConfigBase,
)
from hummingbot.strategy_v2.controllers.market_making_controller_base import MarketMakingControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import PositionSummary
from hummingbot.strategy_v2.executors.dca_executor.data_types import DCAExecutorConfig
from hummingbot.strategy_v2.executors.grid_executor.data_types import GridExecutorConfig
from hummingbot.strategy_v2.executors.order_executor.data_types import OrderExecutorConfig
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, StopExecutorAction
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class BacktestPositionHold:
    """Tracks accumulated position during backtesting, mirroring PositionHold from executor_orchestrator.

    Buys and sells of the same asset net out automatically. Realized PnL comes from
    matched buy/sell volume. Unrealized PnL comes from the remaining net position.
    """

    def __init__(self, connector_name: str, trading_pair: str):
        self.connector_name = connector_name
        self.trading_pair = trading_pair
        self.source_executor_ids: set = set()
        self.buy_amount_base = Decimal("0")
        self.buy_amount_quote = Decimal("0")
        self.sell_amount_base = Decimal("0")
        self.sell_amount_quote = Decimal("0")
        self.cum_fees_quote = Decimal("0")
        self.volume_traded_quote = Decimal("0")

    def add_executor(self, executor_info: ExecutorInfo, entry_price: Decimal):
        """Add an executor's filled position to this hold."""
        self.source_executor_ids.add(executor_info.config.id)
        amount_base = executor_info.filled_amount_quote / entry_price
        if executor_info.side == TradeType.BUY:
            self.buy_amount_base += amount_base
            self.buy_amount_quote += executor_info.filled_amount_quote
        else:
            self.sell_amount_base += amount_base
            self.sell_amount_quote += executor_info.filled_amount_quote
        self.cum_fees_quote += executor_info.cum_fees_quote
        self.volume_traded_quote += executor_info.filled_amount_quote

    @property
    def net_amount_base(self) -> Decimal:
        return self.buy_amount_base - self.sell_amount_base

    @property
    def is_closed(self) -> bool:
        return self.net_amount_base == 0

    def get_position_summary(self, mid_price: Decimal) -> PositionSummary:
        """Calculate position summary with buy/sell netting, mirroring PositionHold.get_position_summary."""
        buy_breakeven = self.buy_amount_quote / self.buy_amount_base if self.buy_amount_base > 0 else Decimal("0")
        sell_breakeven = self.sell_amount_quote / self.sell_amount_base if self.sell_amount_base > 0 else Decimal("0")

        matched_base = min(self.buy_amount_base, self.sell_amount_base)
        realized_pnl = (sell_breakeven - buy_breakeven) * matched_base if matched_base > 0 else Decimal("0")

        net_base = self.buy_amount_base - self.sell_amount_base
        is_net_long = net_base >= 0

        unrealized_pnl = Decimal("0")
        breakeven_price = Decimal("0")
        if net_base != 0:
            if is_net_long:
                remaining_base = net_base
                remaining_quote = self.buy_amount_quote - (matched_base * buy_breakeven)
                breakeven_price = remaining_quote / remaining_base if remaining_base > 0 else Decimal("0")
                unrealized_pnl = (mid_price - breakeven_price) * remaining_base
            else:
                remaining_base = abs(net_base)
                remaining_quote = self.sell_amount_quote - (matched_base * sell_breakeven)
                breakeven_price = remaining_quote / remaining_base if remaining_base > 0 else Decimal("0")
                unrealized_pnl = (breakeven_price - mid_price) * remaining_base

        return PositionSummary(
            connector_name=self.connector_name,
            trading_pair=self.trading_pair,
            volume_traded_quote=self.volume_traded_quote,
            amount=abs(net_base),
            side=TradeType.BUY if is_net_long else TradeType.SELL,
            breakeven_price=breakeven_price,
            unrealized_pnl_quote=unrealized_pnl,
            realized_pnl_quote=realized_pnl,
            cum_fees_quote=self.cum_fees_quote,
        )


class BacktestingEngineBase:
    __controller_class_cache = LazyDict[str, Type[ControllerBase]]()

    def __init__(self):
        self.controller = None
        self.backtesting_resolution = None
        self.backtesting_data_provider = BacktestingDataProvider(connectors={})
        self.position_executor_simulator = PositionExecutorSimulator()
        self.dca_executor_simulator = DCAExecutorSimulator()
        self.grid_executor_simulator = GridExecutorSimulator()
        self.order_executor_simulator = OrderExecutorSimulator()

    @classmethod
    def load_controller_config(cls,
                               config_path: str,
                               controllers_conf_dir_path: str = settings.CONTROLLERS_CONF_DIR_PATH) -> Dict:
        full_path = os.path.join(controllers_conf_dir_path, config_path)
        with open(full_path, 'r') as file:
            config_data = yaml.safe_load(file)
        return config_data

    @classmethod
    def get_controller_config_instance_from_yml(cls,
                                                config_path: str,
                                                controllers_conf_dir_path: str = settings.CONTROLLERS_CONF_DIR_PATH,
                                                controllers_module: str = settings.CONTROLLERS_MODULE) -> ControllerConfigBase:
        config_data = cls.load_controller_config(config_path, controllers_conf_dir_path)
        return cls.get_controller_config_instance_from_dict(config_data, controllers_module)

    @classmethod
    def get_controller_config_instance_from_dict(cls,
                                                 config_data: dict,
                                                 controllers_module: str = settings.CONTROLLERS_MODULE) -> ControllerConfigBase:
        controller_type = config_data.get('controller_type')
        controller_name = config_data.get('controller_name')

        if not controller_type or not controller_name:
            raise ValueError("Missing controller_type or controller_name in the configuration.")

        module_path = f"{controllers_module}.{controller_type}.{controller_name}"
        module = importlib.import_module(module_path)

        config_class = next((member for member_name, member in inspect.getmembers(module)
                             if inspect.isclass(member) and member not in [ControllerConfigBase,
                                                                           MarketMakingControllerConfigBase,
                                                                           DirectionalTradingControllerConfigBase]
                             and (issubclass(member, ControllerConfigBase))), None)
        if not config_class:
            raise InvalidController(f"No configuration class found in the module {controller_name}.")

        return config_class(**config_data)

    async def run_backtesting(self,
                              controller_config: ControllerConfigBase,
                              start: int, end: int,
                              backtesting_resolution: str = "1m",
                              trade_cost=0.0002):
        # Generate unique ID if not set to avoid race conditions
        if not controller_config.id or controller_config.id.strip() == "":
            from hummingbot.strategy_v2.utils.common import generate_unique_id
            controller_config.id = generate_unique_id()

        controller_class = self.__controller_class_cache.get_or_add(controller_config.controller_name, controller_config.get_controller_class)
        # controller_class = controller_config.get_controller_class()
        # Load historical candles
        self.backtesting_data_provider.update_backtesting_time(start, end)
        await self.backtesting_data_provider.initialize_trading_rules(controller_config.connector_name)
        self.controller = controller_class(config=controller_config, market_data_provider=self.backtesting_data_provider,
                                           actions_queue=None)
        self.backtesting_resolution = backtesting_resolution
        await self.initialize_backtesting_data_provider()
        await self.controller.update_processed_data()
        executors_info = await self.simulate_execution(trade_cost=trade_cost)
        key = f"{controller_config.connector_name}_{controller_config.trading_pair}"
        final_price = self.backtesting_data_provider.prices.get(key)
        position_holds_list = list(self.active_position_holds.values())
        results = self.summarize_results(
            executors_info, controller_config.total_amount_quote,
            position_holds=position_holds_list, final_price=final_price,
            pnl_timeseries=self.pnl_timeseries,
        )
        return {
            "executors": executors_info,
            "results": results,
            "processed_data": self.controller.processed_data,
            "position_holds": position_holds_list,
            "position_held_timeseries": self.position_held_timeseries,
            "pnl_timeseries": self.pnl_timeseries,
        }

    async def initialize_backtesting_data_provider(self):
        backtesting_config = CandlesConfig(
            connector=self.controller.config.connector_name,
            trading_pair=self.controller.config.trading_pair,
            interval=self.backtesting_resolution
        )
        await self.controller.market_data_provider.initialize_candles_feed(backtesting_config)
        for config in self.controller.get_candles_config():
            await self.controller.market_data_provider.initialize_candles_feed(config)

    async def simulate_execution(self, trade_cost: float) -> list:
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
        self.active_position_holds: Dict[str, BacktestPositionHold] = {}
        self._position_hold_processed_ids: set = set()
        self._pending_position_hold_executors: List[ExecutorInfo] = []
        self.position_held_timeseries: List[Dict] = []
        self.pnl_timeseries: List[Dict] = []
        self._executor_realized_pnl = 0.0
        self._cumulative_volume = 0.0
        last_index = processed_features.index[-1]
        for i, row in processed_features.iterrows():
            await self.update_state(row)
            for action in self.controller.determine_executor_actions():
                if isinstance(action, CreateExecutorAction):
                    max_ts = self._get_executor_max_timestamp(action.executor_config, last_index)
                    executor_simulation = self.simulate_executor(action.executor_config, processed_features.loc[i:max_ts], trade_cost)
                    if executor_simulation is not None and executor_simulation.close_type != CloseType.FAILED:
                        self.manage_active_executors(executor_simulation)
                elif isinstance(action, StopExecutorAction):
                    self.handle_stop_action(action, row["timestamp"])

        # Final flush: convert any last-tick POSITION_HOLD executors into position holds
        self._update_positions_from_stopped_executors()
        return self.controller.executors_info

    async def update_state(self, row):
        key = f"{self.controller.config.connector_name}_{self.controller.config.trading_pair}"
        self.controller.market_data_provider.prices = {key: Decimal(row["close_bt"])}
        self.controller.market_data_provider._time = row["timestamp"]
        self.controller.processed_data.update(row.to_dict())

        # Step 1: Convert previous tick's stopped POSITION_HOLD executors → position holds
        self._update_positions_from_stopped_executors()

        # Step 2: Check for naturally terminated executors
        self.update_executors_info(row["timestamp"])
        mid_price = Decimal(str(row["close_bt"]))

        # Build positions_held from aggregated position holds (like orchestrator)
        positions_held = []
        for ph in self.active_position_holds.values():
            if not ph.is_closed:
                positions_held.append(ph.get_position_summary(mid_price))
        self.controller.positions_held = positions_held

        # Compute PnL components
        position_realized = sum(float(ps.realized_pnl_quote) for ps in positions_held)
        position_unrealized = sum(float(ps.unrealized_pnl_quote) for ps in positions_held)
        total_pnl = self._executor_realized_pnl + position_realized + position_unrealized

        self.pnl_timeseries.append({
            "timestamp": row["timestamp"],
            "executor_realized_pnl": self._executor_realized_pnl,
            "position_realized_pnl": position_realized,
            "position_unrealized_pnl": position_unrealized,
            "total_pnl": total_pnl,
            "active_executors": len(self.active_executor_simulations),
            "cumulative_volume": self._cumulative_volume,
        })

        # Track position held over time
        if positions_held:
            long_amount = sum(float(ps.amount * mid_price) for ps in positions_held if ps.side == TradeType.BUY)
            short_amount = sum(float(ps.amount * mid_price) for ps in positions_held if ps.side == TradeType.SELL)
            self.position_held_timeseries.append({
                "timestamp": row["timestamp"],
                "long_amount": long_amount,
                "short_amount": short_amount,
                "net_amount": long_amount - short_amount,
                "unrealized_pnl": position_unrealized,
                "realized_pnl": position_realized,
                "n_holds": len([ph for ph in self.active_position_holds.values() if not ph.is_closed]),
            })

    def update_executors_info(self, timestamp: float):
        active_executors_info = []
        simulations_to_remove = []
        for executor in self.active_executor_simulations:
            executor_info = executor.get_executor_info_at_timestamp(timestamp)
            if executor_info.status == RunnableStatus.TERMINATED:
                self.stopped_executors_info.append(executor_info)
                simulations_to_remove.append(executor.config.id)
                # Naturally terminated executors (TP, SL, TL) always count as realized PnL
                self._executor_realized_pnl += float(executor_info.net_pnl_quote)
                self._cumulative_volume += float(executor_info.filled_amount_quote)
            else:
                active_executors_info.append(executor_info)
        self.active_executor_simulations = [es for es in self.active_executor_simulations if es.config.id not in simulations_to_remove]
        self.controller.executors_info = active_executors_info + self.stopped_executors_info

    async def update_processed_data(self, row: pd.Series):
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
        ).add_suffix("_bt")

        if "features" not in self.controller.processed_data:
            backtesting_candles["reference_price"] = backtesting_candles["close_bt"]
            backtesting_candles["spread_multiplier"] = 1
            backtesting_candles["signal"] = 0
        else:
            backtesting_candles = pd.merge_asof(backtesting_candles, self.controller.processed_data["features"],
                                                left_on="timestamp_bt", right_on="timestamp",
                                                direction="backward")

        backtesting_candles["timestamp"] = backtesting_candles["timestamp_bt"]
        # Set timestamp as index to allow index slicing for performance
        backtesting_candles = BacktestingDataProvider.ensure_epoch_index(backtesting_candles)
        backtesting_candles["open"] = backtesting_candles["open_bt"]
        backtesting_candles["high"] = backtesting_candles["high_bt"]
        backtesting_candles["low"] = backtesting_candles["low_bt"]
        backtesting_candles["close"] = backtesting_candles["close_bt"]
        backtesting_candles["volume"] = backtesting_candles["volume_bt"]
        backtesting_candles.dropna(inplace=True)
        self.controller.processed_data["features"] = backtesting_candles
        return backtesting_candles

    def simulate_executor(self, config: Union[PositionExecutorConfig, DCAExecutorConfig, GridExecutorConfig, OrderExecutorConfig],
                          df: pd.DataFrame,
                          trade_cost: float) -> Optional[ExecutorSimulation]:
        """
        Simulates the execution of a trading strategy given a configuration.

        Args:
            config (Union[PositionExecutorConfig, DCAExecutorConfig, GridExecutorConfig, OrderExecutorConfig]): The configuration of the executor.
            df (pd.DataFrame): DataFrame containing the market data from the start time.
            trade_cost (float): The cost per trade.

        Returns:
            ExecutorSimulation: The results of the simulation.
        """
        if isinstance(config, DCAExecutorConfig):
            return self.dca_executor_simulator.simulate(df, config, trade_cost)
        elif isinstance(config, PositionExecutorConfig):
            return self.position_executor_simulator.simulate(df, config, trade_cost)
        elif isinstance(config, GridExecutorConfig):
            trading_rules = None
            try:
                trading_rules = self.backtesting_data_provider.get_trading_rules(
                    config.connector_name, config.trading_pair)
            except (KeyError, AttributeError):
                pass
            return self.grid_executor_simulator.simulate(df, config, trade_cost, trading_rules)
        elif isinstance(config, OrderExecutorConfig):
            return self.order_executor_simulator.simulate(df, config, trade_cost)
        return None

    @staticmethod
    def _get_executor_max_timestamp(config: Union[PositionExecutorConfig, DCAExecutorConfig, GridExecutorConfig, OrderExecutorConfig],
                                    last_index: float) -> float:
        if isinstance(config, OrderExecutorConfig):
            return last_index
        elif isinstance(config, PositionExecutorConfig):
            tl = config.triple_barrier_config.time_limit
        elif isinstance(config, DCAExecutorConfig):
            tl = config.time_limit
        elif isinstance(config, GridExecutorConfig):
            tl = config.triple_barrier_config.time_limit
        else:
            return last_index
        if tl:
            return min(config.timestamp + tl, last_index)
        return last_index

    def manage_active_executors(self, simulation: ExecutorSimulation):
        """
        Manages the list of active executors based on the simulation results.

        Args:
            simulation (ExecutorSimulation): The simulation results of the current executor.
            active_executors (list): The list of active executors.
        """
        if not simulation.executor_simulation.empty:
            self.active_executor_simulations.append(simulation)

    def _update_positions_from_stopped_executors(self):
        """Convert pending POSITION_HOLD executors into BacktestPositionHold entries.

        Mirrors ExecutorOrchestrator._update_positions_from_done_executors():
        drains the pending queue of POSITION_HOLD executors and adds them to
        the aggregated position hold per connector+pair.
        """
        if not self._pending_position_hold_executors:
            return

        for executor_info in self._pending_position_hold_executors:
            entry_price = executor_info.custom_info.get("current_position_average_price")
            if entry_price is not None:
                entry_price = Decimal(str(entry_price))
            else:
                entry_price = Decimal(str(executor_info.custom_info.get("close_price", 0)))

            hold_key = f"{executor_info.config.connector_name}_{executor_info.config.trading_pair}"
            if hold_key not in self.active_position_holds:
                self.active_position_holds[hold_key] = BacktestPositionHold(
                    connector_name=executor_info.config.connector_name,
                    trading_pair=executor_info.config.trading_pair,
                )
            self.active_position_holds[hold_key].add_executor(executor_info, entry_price)
            self._position_hold_processed_ids.add(executor_info.config.id)

        self._pending_position_hold_executors.clear()

    def handle_stop_action(self, action: StopExecutorAction, timestamp: float):
        """
        Handles stop actions for executors, terminating them as required.

        Args:
            action (StopExecutorAction): The action indicating which executor to stop.
            timestamp (float): The current timestamp.
        """
        # Skip if this executor was already processed as a position hold
        if action.executor_id in self._position_hold_processed_ids:
            return

        for executor in self.active_executor_simulations:
            executor_info = executor.get_executor_info_at_timestamp(timestamp)
            if executor_info.config.id == action.executor_id:
                executor_info.status = RunnableStatus.TERMINATED
                executor_info.is_active = False
                executor_info.is_trading = False
                executor_info.close_timestamp = timestamp

                self._cumulative_volume += float(executor_info.filled_amount_quote)
                if action.keep_position and executor_info.filled_amount_quote > 0:
                    executor_info.close_type = CloseType.POSITION_HOLD
                    # Enqueue for position hold creation at START of next tick
                    self._pending_position_hold_executors.append(executor_info)
                else:
                    executor_info.close_type = CloseType.EARLY_STOP
                    self._executor_realized_pnl += float(executor_info.net_pnl_quote)

                self.stopped_executors_info.append(executor_info)
                self.active_executor_simulations.remove(executor)
                return

    @staticmethod
    def summarize_results(executors_info: List, total_amount_quote: float = 1000,
                          position_holds: Optional[List["BacktestPositionHold"]] = None,
                          final_price: Optional[Decimal] = None,
                          pnl_timeseries: Optional[List[Dict]] = None):
        if len(executors_info) > 0:
            executors_df = pd.DataFrame([ei.to_dict() for ei in executors_info])

            # Separate POSITION_HOLD executors — their PnL is tracked in position holds
            non_hold_mask = executors_df["close_type"] != CloseType.POSITION_HOLD
            non_hold_executors = executors_df[non_hold_mask]
            executor_pnl = non_hold_executors["net_pnl_quote"].sum()
            total_fees_quote = float(executors_df["cum_fees_quote"].sum())

            # Position hold PnL (realized from netting + unrealized from net position)
            position_realized_pnl = 0.0
            unrealized_pnl_quote = 0.0
            if position_holds and final_price is not None:
                for ph in position_holds:
                    summary = ph.get_position_summary(final_price)
                    position_realized_pnl += float(summary.realized_pnl_quote)
                    unrealized_pnl_quote += float(summary.unrealized_pnl_quote)

            net_pnl_quote = float(executor_pnl) + position_realized_pnl

            # Close types use ALL executors
            total_executors = executors_df.shape[0]
            executors_df["close_type_name"] = executors_df["close_type"].apply(lambda x: x.name)
            close_types = executors_df.groupby("close_type_name")["timestamp"].count().to_dict()

            # Accuracy and volume metrics use non-hold executors only
            non_hold_with_position = non_hold_executors[non_hold_executors["net_pnl_quote"] != 0]
            total_executors_with_position = non_hold_with_position.shape[0]
            total_volume = non_hold_with_position["filled_amount_quote"].sum()
            total_long = (non_hold_with_position["side"] == TradeType.BUY).sum()
            total_short = (non_hold_with_position["side"] == TradeType.SELL).sum()
            correct_long = ((non_hold_with_position["side"] == TradeType.BUY) & (non_hold_with_position["net_pnl_quote"] > 0)).sum()
            correct_short = ((non_hold_with_position["side"] == TradeType.SELL) & (non_hold_with_position["net_pnl_quote"] > 0)).sum()
            accuracy_long = correct_long / total_long if total_long > 0 else 0
            accuracy_short = correct_short / total_short if total_short > 0 else 0

            total_positions = non_hold_with_position.shape[0]
            win_signals = non_hold_with_position[non_hold_with_position["net_pnl_quote"] > 0]
            loss_signals = non_hold_with_position[non_hold_with_position["net_pnl_quote"] < 0]
            accuracy = (win_signals.shape[0] / total_positions) if total_positions else 0.0

            total_won = win_signals.loc[:, "net_pnl_quote"].sum() if len(win_signals) > 0 else 0
            total_loss = -loss_signals.loc[:, "net_pnl_quote"].sum() if len(loss_signals) > 0 else 0
            profit_factor = total_won / total_loss if total_loss > 0 else 1

            # Use pnl_timeseries for drawdown/sharpe if available (includes position PnL)
            if pnl_timeseries and len(pnl_timeseries) > 1:
                pnl_series = pd.Series([p["total_pnl"] for p in pnl_timeseries])
                peak = np.maximum.accumulate(pnl_series)
                drawdown = pnl_series - peak
                max_draw_down = float(drawdown.min())
                max_drawdown_pct = max_draw_down / float(total_amount_quote)
                returns = pnl_series / float(total_amount_quote)
                sharpe_ratio = float(returns.mean() / returns.std()) if returns.std() > 0 else 0
            elif total_positions > 0:
                cumulative_returns = non_hold_with_position["net_pnl_quote"].cumsum()
                non_hold_with_position = non_hold_with_position.copy()
                non_hold_with_position["cumulative_returns"] = cumulative_returns
                non_hold_with_position["cumulative_volume"] = non_hold_with_position["filled_amount_quote"].cumsum()
                non_hold_with_position["inventory"] = total_amount_quote + cumulative_returns
                peak = np.maximum.accumulate(cumulative_returns)
                drawdown = cumulative_returns - peak
                max_draw_down = float(np.min(drawdown))
                max_drawdown_pct = max_draw_down / non_hold_with_position["inventory"].iloc[0]
                returns = pd.to_numeric(
                    non_hold_with_position["cumulative_returns"] / non_hold_with_position["cumulative_volume"])
                sharpe_ratio = float(returns.mean() / returns.std()) if len(returns) > 1 else 0
            else:
                max_draw_down = 0
                max_drawdown_pct = 0
                sharpe_ratio = 0

            net_pnl_pct = net_pnl_quote / float(total_amount_quote)

            return {
                "net_pnl": float(net_pnl_pct),
                "net_pnl_quote": float(net_pnl_quote),
                "total_executors": int(total_executors),
                "total_executors_with_position": int(total_executors_with_position),
                "total_volume": float(total_volume),
                "total_long": int(total_long),
                "total_short": int(total_short),
                "close_types": close_types,
                "accuracy_long": float(accuracy_long),
                "accuracy_short": float(accuracy_short),
                "total_positions": int(total_positions),
                "accuracy": float(accuracy),
                "max_drawdown_usd": float(max_draw_down),
                "max_drawdown_pct": float(max_drawdown_pct),
                "sharpe_ratio": float(sharpe_ratio),
                "profit_factor": float(profit_factor),
                "win_signals": int(win_signals.shape[0]),
                "loss_signals": int(loss_signals.shape[0]),
                "unrealized_pnl_quote": float(unrealized_pnl_quote),
                "position_realized_pnl_quote": float(position_realized_pnl),
                "total_fees_quote": total_fees_quote,
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
            "unrealized_pnl_quote": 0,
            "position_realized_pnl_quote": 0,
            "total_fees_quote": 0,
        }
