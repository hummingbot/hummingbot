import asyncio
import importlib
import inspect
import logging
import sys
import time
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, Union

from sqlalchemy.orm import Query, Session

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.client.config.config_helpers import ClientConfigAdapter, get_strategy_starter_file
from hummingbot.client.config.strategy_config_data_types import BaseStrategyConfigMap
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.client.settings import SCRIPT_STRATEGIES_MODULE, STRATEGIES
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.connector_manager import ConnectorManager
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.kill_switch import KillSwitch
from hummingbot.exceptions import InvalidScriptModule
from hummingbot.logger import HummingbotLogger
from hummingbot.model.sql_connection_manager import SQLConnectionManager
from hummingbot.model.trade_fill import TradeFill
from hummingbot.notifier.notifier_base import NotifierBase
from hummingbot.strategy.directional_strategy_base import DirectionalStrategyBase
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy.strategy_base import StrategyBase
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase

# Constants
s_decimal_0 = Decimal("0")


class StrategyType(Enum):
    SCRIPT = "script"
    REGULAR = "regular"
    V2 = "v2"


s_logger = None


class TradingCore:
    """
    Core trading functionality with modular architecture.

    This class provides:
    - Connector management (create, add, remove connectors)
    - Market data access (order books, balances, etc.)
    - Strategy management (optional - can run without strategies)
    - Direct trading capabilities
    - Clock management for real-time operations
    """

    KILL_TIMEOUT = 20.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 client_config: Union[ClientConfigMap, ClientConfigAdapter, Dict[str, Any]],
                 scripts_path: Optional[Path] = None):
        """
        Initialize the trading core.

        Args:
            client_config: Configuration object or dictionary
            scripts_path: Optional path to script strategies directory
        """
        # Convert config to ClientConfigAdapter if needed
        if isinstance(client_config, dict):
            self.client_config_map = self._create_config_adapter_from_dict(client_config)
        elif isinstance(client_config, ClientConfigMap):
            self.client_config_map = ClientConfigAdapter(client_config)
        else:
            self.client_config_map = client_config

        # Strategy paths
        self.scripts_path = scripts_path or Path("scripts")

        # Core components
        self.connector_manager = ConnectorManager(self.client_config_map)
        self.clock: Optional[Clock] = None

        # Strategy components (optional)
        self.strategy: Optional[StrategyBase] = None
        self.strategy_name: Optional[str] = None
        self.strategy_config_map: Optional[BaseStrategyConfigMap] = None
        self.strategy_task: Optional[asyncio.Task] = None
        self._strategy_file_name: Optional[str] = None

        # Supporting components
        self.notifiers: List[NotifierBase] = []
        self.kill_switch: Optional[KillSwitch] = None
        self.markets_recorder: Optional[MarketsRecorder] = None
        self.trade_fill_db: Optional[SQLConnectionManager] = None

        # Runtime state
        self.init_time: float = time.time()
        self.start_time: Optional[float] = None
        self._is_running: bool = False
        self._strategy_running: bool = False
        self._trading_required: bool = True

        # Config storage for flexible config loading
        self._config_source: Optional[str] = None
        self._config_data: Optional[Dict[str, Any]] = None

        # Backward compatibility properties
        self.market_trading_pairs_map: Dict[str, List[str]] = {}
        self.market_trading_pair_tuples: List[MarketTradingPairTuple] = []

    def _create_config_adapter_from_dict(self, config_dict: Dict[str, Any]) -> ClientConfigAdapter:
        """Create a ClientConfigAdapter from a dictionary."""
        client_config = ClientConfigMap()

        # Set configuration values
        for key, value in config_dict.items():
            if hasattr(client_config, key):
                setattr(client_config, key, value)

        return ClientConfigAdapter(client_config)

    @property
    def markets(self) -> Dict[str, ExchangeBase]:
        """Get all markets/connectors (backward compatibility)."""
        return self.connector_manager.get_all_connectors()

    @property
    def connectors(self) -> Dict[str, ExchangeBase]:
        """Get all connectors (backward compatibility)."""
        return self.connector_manager.connectors

    @property
    def strategy_file_name(self) -> Optional[str]:
        """Get the strategy file name."""
        return self._strategy_file_name

    @strategy_file_name.setter
    def strategy_file_name(self, value: Optional[str]):
        """Set the strategy file name."""
        self._strategy_file_name = value

    async def start_clock(self) -> bool:
        """
        Start the clock system without requiring a strategy.

        This allows real-time market data updates and order management
        without needing an active strategy.
        """
        if self.clock is not None:
            self.logger().warning("Clock is already running")
            return False

        try:
            tick_size = self.client_config_map.tick_size
            self.logger().info(f"Creating the clock with tick size: {tick_size}")
            self.clock = Clock(ClockMode.REALTIME, tick_size=tick_size)

            # Add all connectors to clock
            for connector in self.connector_manager.connectors.values():
                if connector is not None:
                    self.clock.add_iterator(connector)
                    # Cancel dangling orders
                    if len(connector.limit_orders) > 0:
                        self.logger().info(f"Canceling dangling limit orders on {connector.name}...")
                        await connector.cancel_all(10.0)

            # Start the clock
            self._clock_task = asyncio.create_task(self._run_clock())
            self._is_running = True
            self.start_time = time.time() * 1e3

            self.logger().info("Clock started successfully")
            return True

        except Exception as e:
            self.logger().error(f"Failed to start clock: {e}")
            return False

    async def stop_clock(self) -> bool:
        """Stop the clock system."""
        if self.clock is None:
            return True

        try:
            # Cancel clock task
            if self._clock_task and not self._clock_task.done():
                self._clock_task.cancel()
                try:
                    await self._clock_task
                except asyncio.CancelledError:
                    pass

            self.clock = None
            self._is_running = False

            self.logger().info("Clock stopped successfully")
            return True

        except Exception as e:
            self.logger().error(f"Failed to stop clock: {e}")
            return False

    async def create_connector(self,
                               connector_name: str,
                               trading_pairs: List[str],
                               trading_required: bool = True,
                               api_keys: Optional[Dict[str, str]] = None) -> ExchangeBase:
        """
        Create a connector instance.

        Args:
            connector_name: Name of the connector
            trading_pairs: List of trading pairs
            trading_required: Whether trading is required
            api_keys: Optional API keys

        Returns:
            ExchangeBase: Created connector
        """
        connector = self.connector_manager.create_connector(
            connector_name, trading_pairs, trading_required, api_keys
        )

        # Add to clock if running
        if self.clock and connector:
            self.clock.add_iterator(connector)

        # Add to markets recorder if exists
        if self.markets_recorder and connector:
            self.markets_recorder.add_market(connector)

        return connector

    def remove_connector(self, connector_name: str) -> bool:
        """
        Remove a connector.

        Args:
            connector_name: Name of the connector to remove

        Returns:
            bool: True if successfully removed
        """
        connector = self.connector_manager.get_connector(connector_name)

        if connector:
            # Remove from clock if exists
            connector.stop(self.clock)
            if self.clock:
                self.clock.remove_iterator(connector)

            # Remove from markets recorder if exists
            if self.markets_recorder:
                self.markets_recorder.remove_market(connector)

        return self.connector_manager.remove_connector(connector_name)

    def detect_strategy_type(self, strategy_name: str) -> StrategyType:
        """Detect the type of strategy."""
        if self.is_script_strategy(strategy_name):
            # Check if it's a V2 strategy by examining the script
            return StrategyType.V2 if self._is_v2_script_strategy(strategy_name) else StrategyType.SCRIPT
        elif strategy_name in STRATEGIES:
            return StrategyType.REGULAR
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")

    def is_script_strategy(self, strategy_name: str) -> bool:
        """Check if the strategy is a script strategy."""
        script_file = self.scripts_path / f"{strategy_name}.py"
        return script_file.exists()

    def _is_v2_script_strategy(self, strategy_name: str) -> bool:
        """Check if a script strategy is a V2 strategy."""
        try:
            script_class, _ = self.load_script_class(strategy_name)
            return issubclass(script_class, StrategyV2Base)
        except Exception:
            return False

    def initialize_markets_recorder(self, db_name: str = None):
        """
        Initialize markets recorder for trade persistence.

        Args:
            db_name: Database name (defaults to strategy file name)
        """
        if not db_name:
            # For script strategies with config files, use the config source as db name
            # Otherwise use strategy file name
            if self._config_source and self.is_script_strategy(self.strategy_name or ""):
                db_name = self._config_source
            else:
                db_name = self._strategy_file_name or "trades"

        if db_name.endswith(".yml") or db_name.endswith(".py"):
            db_name = db_name.split(".")[0]

        self.trade_fill_db = SQLConnectionManager.get_trade_fills_instance(
            self.client_config_map, db_name
        )

        self.markets_recorder = MarketsRecorder(
            self.trade_fill_db,
            list(self.connector_manager.connectors.values()),
            self._strategy_file_name or db_name,
            self.strategy_name or db_name,
            self.client_config_map.market_data_collection
        )

        self.markets_recorder.start()
        self.logger().info(f"Markets recorder initialized with database: {db_name}")

    def load_script_class(self, script_name: str) -> Tuple[Type, Optional[BaseClientModel]]:
        """
        Load script strategy class following Hummingbot's pattern.

        Args:
            script_name: Name of the script strategy

        Returns:
            Tuple of (strategy_class, config_object)
        """
        config = None
        module = sys.modules.get(f"{SCRIPT_STRATEGIES_MODULE}.{script_name}")

        if module is not None:
            script_module = importlib.reload(module)
        else:
            script_module = importlib.import_module(f".{script_name}", package=SCRIPT_STRATEGIES_MODULE)

        try:
            script_class = next((member for member_name, member in inspect.getmembers(script_module)
                                 if inspect.isclass(member) and
                                 issubclass(member, ScriptStrategyBase) and
                                 member not in [ScriptStrategyBase, DirectionalStrategyBase, StrategyV2Base]))
        except StopIteration:
            raise InvalidScriptModule(f"The module {script_name} does not contain any subclass of ScriptStrategyBase")

        # Load config if strategy and file names differ
        if self.strategy_name != self._strategy_file_name and self._strategy_file_name:
            try:
                config_class = next((member for member_name, member in inspect.getmembers(script_module)
                                     if inspect.isclass(member) and
                                     issubclass(member, BaseClientModel) and
                                     member not in [BaseClientModel, StrategyV2ConfigBase]))
                # Load config from provided config dict or file
                config_data = self._load_strategy_config()
                config = config_class(**config_data)
                script_class.init_markets(config)
            except StopIteration:
                raise InvalidScriptModule(f"The module {script_name} does not contain any subclass of BaseClientModel")

        return script_class, config

    def _load_strategy_config(self) -> Dict[str, Any]:
        """
        Load strategy configuration from various sources.

        This method can be overridden by subclasses to load from different sources
        (dict, database, remote API, etc.) instead of filesystem.
        """
        if self._config_data:
            return self._config_data
        elif self._config_source:
            # Load from YAML config file
            return self._load_script_yaml_config(self._config_source)
        else:
            return {}

    def _load_script_yaml_config(self, config_file_path: str) -> Dict[str, Any]:
        """Load YAML configuration file for script strategies."""
        import yaml

        from hummingbot.client.settings import SCRIPT_STRATEGY_CONF_DIR_PATH

        try:
            # Try direct path first
            if "/" in config_file_path or "\\" in config_file_path:
                config_path = Path(config_file_path)
            else:
                # Assume it's in the script config directory
                config_path = SCRIPT_STRATEGY_CONF_DIR_PATH / config_file_path

            with open(config_path, 'r') as file:
                return yaml.safe_load(file)
        except Exception as e:
            self.logger().warning(f"Failed to load config file {config_file_path}: {e}")
            return {}

    async def start_strategy(self,
                             strategy_name: str,
                             strategy_config: Optional[Union[BaseStrategyConfigMap, Dict[str, Any], str]] = None,
                             strategy_file_name: Optional[str] = None) -> bool:
        """
        Start a trading strategy.

        Args:
            strategy_name: Name of the strategy
            strategy_config: Strategy configuration (object, dict, or file path)
            strategy_file_name: Optional file name for the strategy

        Returns:
            bool: True if strategy started successfully
        """
        try:
            if self._strategy_running:
                self.logger().warning("Strategy is already running")
                return False

            self.strategy_name = strategy_name
            self._strategy_file_name = strategy_file_name or strategy_name

            # Store config for later use
            if isinstance(strategy_config, str):
                # File path - will be loaded by _load_strategy_config
                self._config_source = strategy_config
            elif isinstance(strategy_config, dict):
                self._config_data = strategy_config

            # Initialize strategy based on type
            strategy_type = self.detect_strategy_type(strategy_name)

            if strategy_type == StrategyType.SCRIPT or strategy_type == StrategyType.V2:
                await self._initialize_script_strategy()
            elif strategy_type == StrategyType.REGULAR:
                await self._initialize_regular_strategy()
            else:
                raise ValueError(f"Unknown strategy type: {strategy_type}")

            # Initialize markets for backward compatibility
            self._initialize_markets_for_strategy()

            # Start the trading execution loop
            await self._start_strategy_execution()

            # Start rate oracle (required for PNL calculation)
            RateOracle.get_instance().start()

            self._strategy_running = True

            self.logger().info(f"Strategy {strategy_name} started successfully")
            return True

        except Exception as e:
            self.logger().error(f"Failed to start strategy {strategy_name}: {e}")
            return False

    async def _initialize_script_strategy(self):
        """Initialize a script strategy using consolidated approach."""
        script_strategy_class, config = self.load_script_class(self.strategy_name)

        # Get markets from script class
        markets_list = []
        for conn, pairs in script_strategy_class.markets.items():
            markets_list.append((conn, list(pairs)))

        # Initialize markets using single method
        self.initialize_markets(markets_list)

        # Create strategy instance
        if config:
            self.strategy = script_strategy_class(self.markets, config)
        else:
            self.strategy = script_strategy_class(self.markets)

    async def _initialize_regular_strategy(self):
        """Initialize a regular strategy using starter file."""
        start_strategy_func: Callable = get_strategy_starter_file(self.strategy_name)
        start_strategy_func(self)

    async def _start_strategy_execution(self):
        """
        Start the strategy execution system.
        """
        try:
            # Ensure markets recorder exists (should have been created during market initialization)
            if not self.markets_recorder:
                self.initialize_markets_recorder()

            # Ensure clock exists
            if self.clock is None:
                await self.start_clock()

            # Add strategy to clock
            if self.strategy and self.clock:
                self.clock.add_iterator(self.strategy)

                # Restore market states if markets recorder exists
                if self.markets_recorder:
                    for market in self.markets.values():
                        self.markets_recorder.restore_market_states(self._strategy_file_name, market)

            # Initialize kill switch if enabled
            if (self._trading_required and
                    self.client_config_map.kill_switch_mode.model_config.get("title") == "kill_switch_enabled"):
                self.kill_switch = self.client_config_map.kill_switch_mode.get_kill_switch(self)
                await self._wait_till_ready(self.kill_switch.start)

            self.logger().info(f"'{self.strategy_name}' strategy execution started.")

        except Exception as e:
            self.logger().error(f"Error starting strategy execution: {e}", exc_info=True)
            raise

    async def _run_clock(self):
        """Run the clock system."""
        with self.clock as clock:
            await clock.run()

    async def _wait_till_ready(self, func: Callable, *args, **kwargs):
        """Wait until all markets are ready before executing function."""
        while True:
            all_ready = all([market.ready for market in self.markets.values()])
            if not all_ready:
                await asyncio.sleep(0.5)
            else:
                if inspect.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)

    async def stop_strategy(self) -> bool:
        """Stop the currently running strategy."""
        try:
            if not self._strategy_running:
                self.logger().warning("No strategy is currently running")
                return False

            # Remove strategy from clock FIRST to prevent further ticks
            if self.clock is not None and self.strategy is not None:
                self.clock.remove_iterator(self.strategy)

            # Remove kill switch from clock
            if self.clock is not None and self.kill_switch is not None:
                self.kill_switch.stop()

            # Stop rate oracle
            RateOracle.get_instance().stop()

            # Clean up strategy components
            self.strategy = None
            self.strategy_task = None
            self.kill_switch = None
            self._strategy_running = False

            self.logger().info("Strategy stopped successfully")
            return True

        except Exception as e:
            self.logger().error(f"Failed to stop strategy: {e}")
            return False

    async def cancel_outstanding_orders(self) -> bool:
        """Cancel all outstanding orders."""
        try:
            cancellation_tasks = []
            for connector in self.connector_manager.connectors.values():
                if len(connector.limit_orders) > 0:
                    cancellation_tasks.append(connector.cancel_all(self.KILL_TIMEOUT))

            if cancellation_tasks:
                await asyncio.gather(*cancellation_tasks, return_exceptions=True)

            return True
        except Exception as e:
            self.logger().error(f"Error cancelling orders: {e}")
            return False

    def _initialize_markets_for_strategy(self):
        """Initialize market data structures for backward compatibility."""
        # Update market trading pairs map
        self.market_trading_pairs_map.clear()
        for name, connector in self.connector_manager.connectors.items():
            self.market_trading_pairs_map[name] = connector.trading_pairs

        # Update market trading pair tuples
        self.market_trading_pair_tuples = [
            MarketTradingPairTuple(connector, trading_pair, base, quote)
            for name, connector in self.connector_manager.connectors.items()
            for trading_pair in connector.trading_pairs
            for base, quote in [trading_pair.split("-")]
        ]

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the trading engine."""
        return {
            'clock_running': self._is_running,
            'strategy_running': self._strategy_running,
            'strategy_name': self.strategy_name,
            'strategy_file_name': self._strategy_file_name,
            'strategy_type': self.detect_strategy_type(self.strategy_name).value if self.strategy_name else None,
            'start_time': self.start_time,
            'uptime': (time.time() * 1e3 - self.start_time) if self.start_time else 0,
            'connectors': self.connector_manager.get_status(),
            'kill_switch_enabled': self.client_config_map.kill_switch_mode.model_config.get("title") == "kill_switch_enabled",
            'markets_recorder_active': self.markets_recorder is not None,
        }

    def add_notifier(self, notifier: NotifierBase):
        """Add a notifier to the engine."""
        self.notifiers.append(notifier)

    def notify(self, msg: str, level: str = "INFO"):
        """Send a notification."""
        self.logger().log(getattr(logging, level.upper(), logging.INFO), msg)
        for notifier in self.notifiers:
            notifier.add_message_to_queue(msg)

    def initialize_markets(self, market_names: List[Tuple[str, List[str]]]):
        """
        Initialize markets - single method that works for all strategy types.

        This replaces all the redundant initialize_markets* methods with one consistent approach.

        Args:
            market_names: List of (exchange_name, trading_pairs) tuples
        """
        # Create connectors for each market
        for connector_name, trading_pairs in market_names:
            connector = self.connector_manager.create_connector(
                connector_name, trading_pairs, self._trading_required
            )

            # Add to clock if running
            if self.clock and connector:
                self.clock.add_iterator(connector)

        # Initialize markets recorder now that connectors exist
        if not self.markets_recorder:
            self.initialize_markets_recorder()

        # Add connectors to markets recorder
        if self.markets_recorder:
            for connector in self.connector_manager.connectors.values():
                self.markets_recorder.add_market(connector)

    def get_balance(self, connector_name: str, asset: str) -> float:
        """Get balance for an asset from a connector."""
        return self.connector_manager.get_balance(connector_name, asset)

    def get_order_book(self, connector_name: str, trading_pair: str):
        """Get order book from a connector."""
        return self.connector_manager.get_order_book(connector_name, trading_pair)

    async def get_current_balances(self, connector_name: str):
        if connector_name in self.connector_manager.connectors and self.connector_manager.connectors[connector_name].ready:
            return self.connector_manager.connectors[connector_name].get_all_balances()
        elif "Paper" in connector_name:
            paper_balances = self.client_config_map.paper_trade.paper_trade_account_balance
            if paper_balances is None:
                return {}
            return {token: Decimal(str(bal)) for token, bal in paper_balances.items()}
        else:
            await self.connector_manager.update_connector_balances(connector_name)
            return self.connector_manager.get_all_balances(connector_name)

    async def calculate_profitability(self) -> Decimal:
        """
        Determines the profitability of the trading bot.
        This function is used by the KillSwitch class.
        Must be updated if the method of performance report gets updated.
        """
        if not self.markets_recorder:
            return s_decimal_0
        if not self.trade_fill_db:
            return s_decimal_0
        if any(not market.ready for market in self.connector_manager.connectors.values()):
            return s_decimal_0

        start_time = self.init_time

        with self.trade_fill_db.get_new_session() as session:
            trades: List[TradeFill] = self._get_trades_from_session(
                int(start_time * 1e3),
                session=session,
                config_file_path=self.strategy_file_name)
            perf_metrics = await self.calculate_performance_metrics_by_connector_pair(trades)
            returns_pct = [perf.return_pct for perf in perf_metrics]
            return sum(returns_pct) / len(returns_pct) if len(returns_pct) > 0 else s_decimal_0

    async def calculate_performance_metrics_by_connector_pair(self, trades: List[TradeFill]) -> List[PerformanceMetrics]:
        """
        Calculates performance metrics by connector and trading pair using the provided trades and the PerformanceMetrics class.
        """
        market_info: Set[Tuple[str, str]] = set((t.market, t.symbol) for t in trades)
        performance_metrics: List[PerformanceMetrics] = []
        for market, symbol in market_info:
            cur_trades = [t for t in trades if t.market == market and t.symbol == symbol]
            network_timeout = float(self.client_config_map.commands_timeout.other_commands_timeout)
            try:
                cur_balances = await asyncio.wait_for(self.get_current_balances(market), network_timeout)
            except asyncio.TimeoutError:
                self.logger().warning("\nA network error prevented the balances retrieval to complete. See logs for more details.")
                raise
            perf = await PerformanceMetrics.create(symbol, cur_trades, cur_balances)
            performance_metrics.append(perf)
        return performance_metrics

    @staticmethod
    def _get_trades_from_session(start_timestamp: int,
                                 session: Session,
                                 number_of_rows: Optional[int] = None,
                                 config_file_path: str = None) -> List[TradeFill]:

        filters = [TradeFill.timestamp >= start_timestamp]
        if config_file_path is not None:
            filters.append(TradeFill.config_file_path.like(f"%{config_file_path}%"))
        query: Query = (session
                        .query(TradeFill)
                        .filter(*filters)
                        .order_by(TradeFill.timestamp.desc()))
        if number_of_rows is None:
            result: List[TradeFill] = query.all() or []
        else:
            result: List[TradeFill] = query.limit(number_of_rows).all() or []

        result.reverse()
        return result

    async def shutdown(self, skip_order_cancellation: bool = False) -> bool:
        """
        Shutdown the trading core completely.

        This stops all strategies, connectors, and the clock.

        Args:
            skip_order_cancellation: Whether to skip cancelling outstanding orders
        """
        try:
            # Handle script strategy specific cleanup first
            if self.strategy and isinstance(self.strategy, ScriptStrategyBase):
                await self.strategy.on_stop()

            # Stop strategy if running
            if self._strategy_running:
                await self.stop_strategy()

            # Cancel outstanding orders
            if not skip_order_cancellation:
                await self.cancel_outstanding_orders()

            # Remove all connectors
            connector_names = list(self.connector_manager.connectors.keys())
            for name in connector_names:
                try:
                    self.remove_connector(name)
                except Exception as e:
                    self.logger().error(f"Error stopping connector {name}: {e}")

            # Stop clock if running
            if self._is_running:
                await self.stop_clock()

            # Stop markets recorder
            if self.markets_recorder:
                self.markets_recorder.stop()
                self.markets_recorder = None

            # Clear strategy references
            self.strategy = None
            self.strategy_name = None
            self.strategy_config_map = None
            self._strategy_file_name = None
            self._config_source = None
            self._config_data = None

            self.logger().info("Trading core shutdown complete")
            return True

        except Exception as e:
            self.logger().error(f"Error during shutdown: {e}")
            return False
