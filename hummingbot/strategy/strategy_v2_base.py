import asyncio
import importlib
import inspect
import os
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Set

import pandas as pd
import yaml
from pydantic import Field, field_validator

from hummingbot.client import settings
from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import MarketDict, PositionMode
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.data_feed.market_data_provider import MarketDataProvider
from hummingbot.exceptions import InvalidController
from hummingbot.remote_iface.mqtt import ETopicPublisher
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.controllers.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerConfigBase,
)
from hummingbot.strategy_v2.controllers.market_making_controller_base import MarketMakingControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import PositionSummary
from hummingbot.strategy_v2.executors.executor_orchestrator import ExecutorOrchestrator
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executor_actions import (
    CreateExecutorAction,
    ExecutorAction,
    StopExecutorAction,
    StoreExecutorAction,
)
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class StrategyV2ConfigBase(BaseClientModel):
    """
    Base class for version 2 strategy configurations.
    """
    markets: MarketDict = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter markets in format 'exchange1.tp1,tp2:exchange2.tp1,tp2':",
            "prompt_on_new": True}
    )
    candles_config: List[CandlesConfig] = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter candle configs in format 'exchange1.tp1.interval1.max_records:exchange2.tp2.interval2.max_records':",
            "prompt_on_new": True,
        }
    )
    controllers_config: List[str] = Field(
        default=[],
        json_schema_extra={
            "prompt": "Enter controller configurations (comma-separated file paths), leave it empty if none: ",
            "prompt_on_new": True,
        }
    )

    @field_validator("controllers_config", mode="before")
    @classmethod
    def parse_controllers_config(cls, v):
        # Parse string input into a list of file pathsq
        if isinstance(v, str):
            if v == "":
                return []
            return [item.strip() for item in v.split(',') if item.strip()]
        if v is None:
            return []
        return v

    def load_controller_configs(self):
        loaded_configs = []
        for config_path in self.controllers_config:
            full_path = os.path.join(settings.CONTROLLERS_CONF_DIR_PATH, config_path)
            with open(full_path, 'r') as file:
                config_data = yaml.safe_load(file)

            controller_type = config_data.get('controller_type')
            controller_name = config_data.get('controller_name')

            if not controller_type or not controller_name:
                raise ValueError(f"Missing controller_type or controller_name in {config_path}")

            module_path = f"{settings.CONTROLLERS_MODULE}.{controller_type}.{controller_name}"
            module = importlib.import_module(module_path)

            config_class = next((member for member_name, member in inspect.getmembers(module)
                                 if inspect.isclass(member) and member not in [ControllerConfigBase,
                                                                               MarketMakingControllerConfigBase,
                                                                               DirectionalTradingControllerConfigBase]
                                 and (issubclass(member, ControllerConfigBase))), None)
            if not config_class:
                raise InvalidController(f"No configuration class found in the module {controller_name}.")

            loaded_configs.append(config_class(**config_data))

        return loaded_configs

    @field_validator('markets', mode="before")
    @classmethod
    def parse_markets(cls, v) -> Dict[str, Set[str]]:
        if isinstance(v, str):
            return cls.parse_markets_str(v)
        elif isinstance(v, dict):
            return v
        raise ValueError("Invalid type for markets. Expected str or Dict[str, Set[str]]")

    @staticmethod
    def parse_markets_str(v: str) -> Dict[str, Set[str]]:
        markets_dict = {}
        if v.strip():
            exchanges = v.split(':')
            for exchange in exchanges:
                parts = exchange.split('.')
                if len(parts) != 2 or not parts[1]:
                    raise ValueError(f"Invalid market format in segment '{exchange}'. "
                                     "Expected format: 'exchange.tp1,tp2'")
                exchange_name, trading_pairs = parts
                markets_dict[exchange_name] = set(trading_pairs.split(','))
        return markets_dict

    @field_validator('candles_config', mode="before")
    @classmethod
    def parse_candles_config(cls, v) -> List[CandlesConfig]:
        if isinstance(v, str):
            return cls.parse_candles_config_str(v)
        elif isinstance(v, list):
            return v
        raise ValueError("Invalid type for candles_config. Expected str or List[CandlesConfig]")

    @staticmethod
    def parse_candles_config_str(v: str) -> List[CandlesConfig]:
        configs = []
        if v.strip():
            entries = v.split(':')
            for entry in entries:
                parts = entry.split('.')
                if len(parts) != 4:
                    raise ValueError(f"Invalid candles config format in segment '{entry}'. "
                                     "Expected format: 'exchange.tradingpair.interval.maxrecords'")
                connector, trading_pair, interval, max_records_str = parts
                try:
                    max_records = int(max_records_str)
                except ValueError:
                    raise ValueError(f"Invalid max_records value '{max_records_str}' in segment '{entry}'. "
                                     "max_records should be an integer.")
                config = CandlesConfig(
                    connector=connector,
                    trading_pair=trading_pair,
                    interval=interval,
                    max_records=max_records
                )
                configs.append(config)
        return configs


class StrategyV2Base(ScriptStrategyBase):
    """
    V2StrategyBase is a base class for strategies that use the new smart components architecture.
    """
    markets: Dict[str, Set[str]]
    _last_config_update_ts: float = 0
    closed_executors_buffer: int = 100
    max_executors_close_attempts: int = 10
    config_update_interval: int = 10

    @classmethod
    def init_markets(cls, config: StrategyV2ConfigBase):
        """
        Initialize the markets that the strategy is going to use. This method is called when the strategy is created in
        the start command. Can be overridden to implement custom behavior.
        """
        markets = MarketDict(config.markets)
        controllers_configs = config.load_controller_configs()
        for controller_config in controllers_configs:
            markets = controller_config.update_markets(markets)
        cls.markets = markets

    def __init__(self, connectors: Dict[str, ConnectorBase], config: Optional[StrategyV2ConfigBase] = None):
        super().__init__(connectors, config)
        self.config = config

        # Initialize empty dictionaries to hold controllers and unified controller reports
        self.controllers: Dict[str, ControllerBase] = {}
        self.controller_reports: Dict[str, Dict] = {}

        # Initialize the market data provider and executor orchestrator
        self.market_data_provider = MarketDataProvider(connectors)
        self.market_data_provider.initialize_candles_feed_list(config.candles_config)

        # Initialize the controllers
        self.actions_queue = asyncio.Queue()
        self.listen_to_executor_actions_task: asyncio.Task = asyncio.create_task(self.listen_to_executor_actions())
        self.initialize_controllers()
        self._is_stop_triggered = False

        # Collect initial positions from all controller configs
        self.executor_orchestrator = ExecutorOrchestrator(
            strategy=self,
            initial_positions_by_controller=self._collect_initial_positions()
        )
        self.mqtt_enabled = False
        self._pub: Optional[ETopicPublisher] = None

    def start(self, clock: Clock, timestamp: float) -> None:
        """
        Start the strategy.
        :param clock: Clock to use.
        :param timestamp: Current time.
        """
        self._last_timestamp = timestamp
        self.apply_initial_setting()
        # Check if MQTT is enabled at runtime
        from hummingbot.client.hummingbot_application import HummingbotApplication
        if HummingbotApplication.main_application()._mqtt is not None:
            self.mqtt_enabled = True
            self._pub = ETopicPublisher("performance", use_bot_prefix=True)

        # Start controllers
        for controller in self.controllers.values():
            controller.start()

    def apply_initial_setting(self):
        """
        Apply initial settings for the strategy, such as setting position mode and leverage for all connectors.
        """
        pass

    def _collect_initial_positions(self) -> Dict[str, List]:
        """
        Collect initial positions from all controller configurations.
        Returns a dictionary mapping controller_id -> list of InitialPositionConfig.
        """
        if not self.config:
            return {}

        initial_positions_by_controller = {}
        try:
            controllers_configs = self.config.load_controller_configs()
            for controller_config in controllers_configs:
                if hasattr(controller_config, 'initial_positions') and controller_config.initial_positions:
                    initial_positions_by_controller[controller_config.id] = controller_config.initial_positions
        except Exception as e:
            self.logger().error(f"Error collecting initial positions: {e}", exc_info=True)

        return initial_positions_by_controller

    def initialize_controllers(self):
        """
        Initialize the controllers based on the provided configuration.
        """
        controllers_configs = self.config.load_controller_configs()
        for controller_config in controllers_configs:
            self.add_controller(controller_config)
            MarketsRecorder.get_instance().store_controller_config(controller_config)

    def add_controller(self, config: ControllerConfigBase):
        try:
            controller = config.get_controller_class()(config, self.market_data_provider, self.actions_queue)
            self.controllers[config.id] = controller
        except Exception as e:
            self.logger().error(f"Error adding controller: {e}", exc_info=True)

    def update_controllers_configs(self):
        """
        Update the controllers configurations based on the provided configuration.
        """
        if self._last_config_update_ts + self.config_update_interval < self.current_timestamp:
            self._last_config_update_ts = self.current_timestamp
            controllers_configs = self.config.load_controller_configs()
            for controller_config in controllers_configs:
                if controller_config.id in self.controllers:
                    self.controllers[controller_config.id].update_config(controller_config)
                else:
                    self.add_controller(controller_config)

    async def listen_to_executor_actions(self):
        """
        Asynchronously listen to actions from the controllers and execute them.
        """
        while True:
            try:
                actions = await self.actions_queue.get()
                self.executor_orchestrator.execute_actions(actions)
                self.update_executors_info()
                controller_id = actions[0].controller_id
                controller = self.controllers.get(controller_id)
                controller.executors_info = self.get_executors_by_controller(controller_id)
                controller.executors_update_event.set()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Error executing action: {e}", exc_info=True)

    def update_executors_info(self):
        """
        Update the unified controller reports and publish the updates to the active controllers.
        """
        try:
            # Get all reports in a single call and store them
            self.controller_reports = self.executor_orchestrator.get_all_reports()

            # Update each controller with its specific data
            for controller_id, controller in self.controllers.items():
                controller_report = self.controller_reports.get(controller_id, {})
                controller.executors_info = controller_report.get("executors", [])
                controller.positions_held = controller_report.get("positions", [])
                controller.executors_update_event.set()
        except Exception as e:
            self.logger().error(f"Error updating controller reports: {e}", exc_info=True)

    @staticmethod
    def is_perpetual(connector: str) -> bool:
        return "perpetual" in connector

    async def on_stop(self):
        self._is_stop_triggered = True
        self.listen_to_executor_actions_task.cancel()
        await self.executor_orchestrator.stop(self.max_executors_close_attempts)
        for controller in self.controllers.values():
            controller.stop()
        self.market_data_provider.stop()
        self.executor_orchestrator.store_all_executors()
        if self.mqtt_enabled:
            self._pub({controller_id: {} for controller_id in self.controllers.keys()})
            self._pub = None

    def on_tick(self):
        self.update_executors_info()
        self.update_controllers_configs()
        if self.market_data_provider.ready and not self._is_stop_triggered:
            executor_actions: List[ExecutorAction] = self.determine_executor_actions()
            for action in executor_actions:
                self.executor_orchestrator.execute_action(action)

    def determine_executor_actions(self) -> List[ExecutorAction]:
        """
        Determine actions based on the provided executor handler report.
        """
        actions = []
        actions.extend(self.create_actions_proposal())
        actions.extend(self.stop_actions_proposal())
        actions.extend(self.store_actions_proposal())
        return actions

    def create_actions_proposal(self) -> List[CreateExecutorAction]:
        """
        Create actions proposal based on the current state of the executors.
        """
        raise NotImplementedError

    def stop_actions_proposal(self) -> List[StopExecutorAction]:
        """
        Create a list of actions to stop the executors based on order refresh and early stop conditions.
        """
        raise NotImplementedError

    def store_actions_proposal(self) -> List[StoreExecutorAction]:
        """
        Create a list of actions to store the executors that have been stopped.
        """
        potential_executors_to_store = self.filter_executors(
            executors=self.get_all_executors(),
            filter_func=lambda x: x.is_done)
        sorted_executors = sorted(potential_executors_to_store, key=lambda x: x.timestamp, reverse=True)
        if len(sorted_executors) > self.closed_executors_buffer:
            return [StoreExecutorAction(executor_id=executor.id, controller_id=executor.controller_id) for executor in
                    sorted_executors[self.closed_executors_buffer:]]
        return []

    def get_executors_by_controller(self, controller_id: str) -> List[ExecutorInfo]:
        """Get executors for a specific controller from the unified reports."""
        return self.controller_reports.get(controller_id, {}).get("executors", [])

    def get_all_executors(self) -> List[ExecutorInfo]:
        """Get all executors from all controllers."""
        return [executor for executors_list in [report.get("executors", []) for report in self.controller_reports.values()] for executor in executors_list]

    def get_positions_by_controller(self, controller_id: str) -> List[PositionSummary]:
        """Get positions for a specific controller from the unified reports."""
        return self.controller_reports.get(controller_id, {}).get("positions", [])

    def get_performance_report(self, controller_id: str):
        """Get performance report for a specific controller."""
        return self.controller_reports.get(controller_id, {}).get("performance")

    def set_leverage(self, connector: str, trading_pair: str, leverage: int):
        self.connectors[connector].set_leverage(trading_pair, leverage)

    def set_position_mode(self, connector: str, position_mode: PositionMode):
        self.connectors[connector].set_position_mode(position_mode)

    @staticmethod
    def filter_executors(executors: List[ExecutorInfo], filter_func: Callable[[ExecutorInfo], bool]) -> List[ExecutorInfo]:
        return [executor for executor in executors if filter_func(executor)]

    @staticmethod
    def executors_info_to_df(executors_info: List[ExecutorInfo]) -> pd.DataFrame:
        """
        Convert a list of executor handler info to a dataframe.
        """
        df = pd.DataFrame([ei.to_dict() for ei in executors_info])
        # Convert the enum values to integers
        df['status'] = df['status'].apply(lambda x: x.value)

        # Sort the DataFrame
        df.sort_values(by='status', ascending=True, inplace=True)

        # Convert back to enums for display
        df['status'] = df['status'].apply(RunnableStatus)
        return df

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."

        lines = []
        warning_lines = []
        warning_lines.extend(self.network_warning(self.get_market_trading_pair_tuples()))

        # Basic account info
        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        try:
            df = self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])

        # Controller sections
        performance_data = []

        for controller_id, controller in self.controllers.items():
            lines.append(f"\n{'=' * 60}")
            lines.append(f"Controller: {controller_id}")
            lines.append(f"{'=' * 60}")

            # Controller status
            lines.extend(controller.to_format_status())

            # Last 6 executors table
            executors_list = self.get_executors_by_controller(controller_id)
            if executors_list:
                lines.append("\n  Recent Executors (Last 6):")
                # Sort by timestamp and take last 6
                recent_executors = sorted(executors_list, key=lambda x: x.timestamp, reverse=True)[:6]
                executors_df = self.executors_info_to_df(recent_executors)
                if not executors_df.empty:
                    executors_df["age"] = self.current_timestamp - executors_df["timestamp"]
                    executor_columns = ["type", "side", "status", "net_pnl_pct", "net_pnl_quote",
                                        "filled_amount_quote", "is_trading", "close_type", "age"]
                    available_columns = [col for col in executor_columns if col in executors_df.columns]
                    lines.append(format_df_for_printout(executors_df[available_columns],
                                                        table_format="psql", index=False))
            else:
                lines.append("  No executors found.")

            # Positions table
            positions = self.get_positions_by_controller(controller_id)
            if positions:
                lines.append("\n  Positions Held:")
                positions_data = []
                for pos in positions:
                    positions_data.append({
                        "Connector": pos.connector_name,
                        "Trading Pair": pos.trading_pair,
                        "Side": pos.side.name,
                        "Amount": f"{pos.amount:.4f}",
                        "Value (USD)": f"${pos.amount * pos.breakeven_price:.2f}",
                        "Breakeven Price": f"{pos.breakeven_price:.6f}",
                        "Unrealized PnL": f"${pos.unrealized_pnl_quote:+.2f}",
                        "Realized PnL": f"${pos.realized_pnl_quote:+.2f}",
                        "Fees": f"${pos.cum_fees_quote:.2f}"
                    })
                positions_df = pd.DataFrame(positions_data)
                lines.append(format_df_for_printout(positions_df, table_format="psql", index=False))
            else:
                lines.append("  No positions held.")

            # Collect performance data for summary table
            performance_report = self.get_performance_report(controller_id)
            if performance_report:
                performance_data.append({
                    "Controller": controller_id,
                    "Realized PnL": f"${performance_report.realized_pnl_quote:.2f}",
                    "Unrealized PnL": f"${performance_report.unrealized_pnl_quote:.2f}",
                    "Global PnL": f"${performance_report.global_pnl_quote:.2f}",
                    "Global PnL %": f"{performance_report.global_pnl_pct:.2f}%",
                    "Volume Traded": f"${performance_report.volume_traded:.2f}"
                })

        # Performance summary table
        if performance_data:
            lines.append(f"\n{'=' * 80}")
            lines.append("PERFORMANCE SUMMARY")
            lines.append(f"{'=' * 80}")

            # Calculate global totals
            global_realized = sum(Decimal(p["Realized PnL"].replace("$", "")) for p in performance_data)
            global_unrealized = sum(Decimal(p["Unrealized PnL"].replace("$", "")) for p in performance_data)
            global_total = global_realized + global_unrealized
            global_volume = sum(Decimal(p["Volume Traded"].replace("$", "")) for p in performance_data)
            global_pnl_pct = (global_total / global_volume) * 100 if global_volume > 0 else Decimal(0)

            # Add global row
            performance_data.append({
                "Controller": "GLOBAL TOTAL",
                "Realized PnL": f"${global_realized:.2f}",
                "Unrealized PnL": f"${global_unrealized:.2f}",
                "Global PnL": f"${global_total:.2f}",
                "Global PnL %": f"{global_pnl_pct:.2f}%",
                "Volume Traded": f"${global_volume:.2f}"
            })

            performance_df = pd.DataFrame(performance_data)
            lines.append(format_df_for_printout(performance_df, table_format="psql", index=False))

        return "\n".join(lines)
