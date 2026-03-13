import asyncio
import importlib
import inspect
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

from pydantic import ConfigDict, Field, field_validator

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.core.data_type.common import MarketDict, PositionAction, PriceType, TradeType
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.data_feed.market_data_provider import MarketDataProvider
from hummingbot.strategy_v2.executors.order_executor.data_types import (
    ExecutionStrategy,
    LimitChaserConfig,
    OrderExecutorConfig,
)
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction, StopExecutorAction
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo, PerformanceReport
from hummingbot.strategy_v2.models.position_config import InitialPositionConfig
from hummingbot.strategy_v2.runnable_base import RunnableBase

if TYPE_CHECKING:
    from hummingbot.strategy_v2.executors.data_types import PositionSummary


@dataclass
class ExecutorFilter:
    """
    Filter criteria for filtering executors. All criteria are optional and use AND logic.
    List-based criteria use OR logic within the list.
    """
    executor_ids: Optional[List[str]] = None
    connector_names: Optional[List[str]] = None
    trading_pairs: Optional[List[str]] = None
    executor_types: Optional[List[str]] = None
    statuses: Optional[List[RunnableStatus]] = None
    sides: Optional[List[TradeType]] = None
    is_active: Optional[bool] = None
    is_trading: Optional[bool] = None
    close_types: Optional[List[CloseType]] = None
    controller_ids: Optional[List[str]] = None
    min_pnl_pct: Optional[Decimal] = None
    max_pnl_pct: Optional[Decimal] = None
    min_pnl_quote: Optional[Decimal] = None
    max_pnl_quote: Optional[Decimal] = None
    min_timestamp: Optional[float] = None
    max_timestamp: Optional[float] = None
    min_close_timestamp: Optional[float] = None
    max_close_timestamp: Optional[float] = None


class ControllerConfigBase(BaseClientModel):
    """
    This class represents the base configuration for a controller in the Hummingbot trading bot.
    It inherits from the Pydantic BaseModel and includes several fields that are used to configure a controller.

    Attributes:
        id (str): A unique identifier for the controller. Required.
        controller_name (str): The name of the trading strategy that the controller will use.
        candles_config (List[CandlesConfig]): A list of configurations for the candles data feed.
    """
    id: str = Field(..., description="Unique identifier for the controller. Required.")
    controller_name: str
    controller_type: str = "generic"
    total_amount_quote: Decimal = Field(
        default=Decimal("100"),
        json_schema_extra={
            "prompt": "Enter the total amount in quote asset to use for trading (e.g., 1000): ",
            "prompt_on_new": True,
            "is_updatable": True
        }
    )
    manual_kill_switch: bool = Field(default=False, json_schema_extra={"is_updatable": True})
    initial_positions: List[InitialPositionConfig] = Field(
        default=[],
        json_schema_extra={
            "prompt": "Enter initial positions as a list of InitialPositionConfig objects: ",
            "prompt_on_new": False,
            "is_updatable": False
        })
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator('initial_positions', mode="before")
    @classmethod
    def parse_initial_positions(cls, v) -> List[InitialPositionConfig]:
        if isinstance(v, list):
            return v
        raise ValueError("Invalid type for initial_positions. Expected List[InitialPositionConfig]")

    def update_markets(self, markets: MarketDict) -> MarketDict:
        """
        Update the markets dict of the script from the config.
        """
        return markets

    def set_id(self, id_value: str = None):
        """
        Set the ID for the controller config. If no ID is provided, generate a unique one.
        """
        if id_value is None:
            from hummingbot.strategy_v2.utils.common import generate_unique_id
            return generate_unique_id()
        return id_value

    def get_controller_class(self):
        """
        Dynamically load and return the controller class based on the controller configuration.
        """
        try:
            module = importlib.import_module(self.__module__)
            base_classes = ["ControllerBase", "MarketMakingControllerBase", "DirectionalTradingControllerBase"]
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, ControllerBase) and obj.__name__ not in base_classes:
                    return obj
        except ImportError as e:
            raise ImportError(f"Could not import the module: {self.__module__}. Error: {str(e)}")

        raise ValueError(f"No valid controller class found for module: {self.__module__}")


class ControllerBase(RunnableBase):
    """
    Base class for controllers.

    This class provides comprehensive executor filtering capabilities through the ExecutorFilter
    system and convenience methods for common trading operations.

    Filtering Examples:
    ==================

    # Get all active executors
    active_executors = controller.get_active_executors()

    # Get active executors for specific connectors and pairs
    binance_btc_executors = controller.get_active_executors(
        connector_names=['binance'],
        trading_pairs=['BTC-USDT']
    )

    # Get completed executors with profit filtering
    profitable_executors = controller.get_completed_executors()
    profitable_filter = ExecutorFilter(min_pnl_pct=Decimal('0.01'))
    profitable_executors = controller.filter_executors(executor_filter=profitable_filter)

    # Get executors by type
    position_executors = controller.get_executors_by_type(['PositionExecutor'])

    # Get buy-only executors
    buy_executors = controller.get_executors_by_side([TradeType.BUY])

    # Advanced filtering with ExecutorFilter
    import time
    complex_filter = ExecutorFilter(
        connector_names=['binance', 'coinbase'],
        trading_pairs=['BTC-USDT', 'ETH-USDT'],
        executor_types=['PositionExecutor', 'DCAExecutor'],
        sides=[TradeType.BUY],
        is_active=True,
        min_pnl_pct=Decimal('-0.05'),  # Max 5% loss
        max_pnl_pct=Decimal('0.10'),   # Max 10% profit
        min_timestamp=time.time() - 3600  # Last hour only
    )
    filtered_executors = controller.filter_executors(executor_filter=complex_filter)

    # Filter open orders with advanced criteria
    recent_orders = controller.open_orders(
        executor_filter=ExecutorFilter(
            executor_types=['PositionExecutor'],
            min_timestamp=time.time() - 1800  # Last 30 minutes
        )
    )

    # Cancel specific types of orders
    cancelled_ids = controller.cancel_all(
        executor_filter=ExecutorFilter(
            sides=[TradeType.SELL],
            executor_types=['PositionExecutor']
        )
    )

    # Get positions with PnL filters
    losing_positions = controller.open_positions(
        executor_filter=ExecutorFilter(
            max_pnl_pct=Decimal('-0.02')  # More than 2% loss
        )
    )
    """

    def __init__(self, config: ControllerConfigBase, market_data_provider: MarketDataProvider,
                 actions_queue: asyncio.Queue, update_interval: float = 1.0):
        super().__init__(update_interval=update_interval)
        self.config = config
        self.executors_info: List[ExecutorInfo] = []
        self.positions_held: List[PositionSummary] = []
        self.performance_report: Optional[PerformanceReport] = None
        self.market_data_provider: MarketDataProvider = market_data_provider
        self.actions_queue: asyncio.Queue = actions_queue
        self.processed_data = {}
        self.executors_update_event = asyncio.Event()
        self.executors_info_queue = asyncio.Queue()

    def start(self):
        """
        Allow controllers to be restarted after being stopped.
        """
        if self._status != RunnableStatus.RUNNING:
            self.terminated.clear()
            self._status = RunnableStatus.RUNNING
            self.executors_update_event.set()
            safe_ensure_future(self.control_loop())
        self.initialize_candles()

    def initialize_candles(self):
        """
        Initialize candles for the controller. This method calls get_candles_config()
        which can be overridden by controllers that need candles data.
        """
        candles_configs = self.get_candles_config()
        for candles_config in candles_configs:
            self.market_data_provider.initialize_candles_feed(candles_config)

    def get_candles_config(self) -> List[CandlesConfig]:
        """
        Override this method in your controller to specify candles configuration.
        By default, returns empty list (no candles).

        Example:
        ```python
        def get_candles_config(self) -> List[CandlesConfig]:
            return [CandlesConfig(
                connector=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                interval="1m",
                max_records=100
            )]
        ```

        Returns:
            List[CandlesConfig]: List of candles configurations
        """
        return []

    def update_config(self, new_config: ControllerConfigBase):
        """
        Update the controller configuration. With the variables that in the client_data have the is_updatable flag set
        to True. This will be only available for those variables that don't interrupt the bot operation.
        """
        for name, field_info in self.config.__class__.model_fields.items():
            json_schema_extra = field_info.json_schema_extra or {}
            if json_schema_extra.get("is_updatable", False):
                setattr(self.config, name, getattr(new_config, name))

    async def control_task(self):
        if self.market_data_provider.ready and self.executors_update_event.is_set():
            await self.update_processed_data()
            executor_actions: List[ExecutorAction] = self.determine_executor_actions()
            if len(executor_actions) > 0:
                self.logger().debug(f"Sending actions: {executor_actions}")
                await self.send_actions(executor_actions)

    async def send_actions(self, executor_actions: List[ExecutorAction]):
        if len(executor_actions) > 0:
            await self.actions_queue.put(executor_actions)
            self.executors_update_event.clear()  # Clear the event after sending the actions

    def filter_executors(self, executors: List[ExecutorInfo] = None, executor_filter: ExecutorFilter = None, filter_func: Callable[[ExecutorInfo], bool] = None) -> List[ExecutorInfo]:
        """
        Filter executors using ExecutorFilter criteria or a custom filter function.

        :param executors: Optional list of executors to filter. If None, uses self.executors_info
        :param executor_filter: ExecutorFilter instance with filtering criteria
        :param filter_func: Optional custom filter function for backward compatibility
        :return: List of filtered ExecutorInfo objects
        """
        filtered_executors = (executors or self.executors_info).copy()

        # Apply custom filter function if provided (backward compatibility)
        if filter_func:
            filtered_executors = [executor for executor in filtered_executors if filter_func(executor)]

        # Apply ExecutorFilter criteria if provided
        if executor_filter:
            filtered_executors = self._apply_executor_filter(filtered_executors, executor_filter)

        return filtered_executors

    def _apply_executor_filter(self, executors: List[ExecutorInfo], executor_filter: ExecutorFilter) -> List[ExecutorInfo]:
        """Apply ExecutorFilter criteria to a list of executors."""
        filtered = executors

        # Filter by executor IDs
        if executor_filter.executor_ids:
            filtered = [e for e in filtered if e.id in executor_filter.executor_ids]

        # Filter by connector names
        if executor_filter.connector_names:
            filtered = [e for e in filtered if e.connector_name in executor_filter.connector_names]

        # Filter by trading pairs
        if executor_filter.trading_pairs:
            filtered = [e for e in filtered if e.trading_pair in executor_filter.trading_pairs]

        # Filter by executor types
        if executor_filter.executor_types:
            filtered = [e for e in filtered if e.type in executor_filter.executor_types]

        # Filter by statuses
        if executor_filter.statuses:
            filtered = [e for e in filtered if e.status in executor_filter.statuses]

        # Filter by sides
        if executor_filter.sides:
            filtered = [e for e in filtered if e.side in executor_filter.sides]

        # Filter by active state
        if executor_filter.is_active is not None:
            filtered = [e for e in filtered if e.is_active == executor_filter.is_active]

        # Filter by trading state
        if executor_filter.is_trading is not None:
            filtered = [e for e in filtered if e.is_trading == executor_filter.is_trading]

        # Filter by close types
        if executor_filter.close_types:
            filtered = [e for e in filtered if e.close_type in executor_filter.close_types]

        # Filter by controller IDs
        if executor_filter.controller_ids:
            filtered = [e for e in filtered if e.controller_id in executor_filter.controller_ids]

        # Filter by PnL percentage range
        if executor_filter.min_pnl_pct is not None:
            filtered = [e for e in filtered if e.net_pnl_pct >= executor_filter.min_pnl_pct]
        if executor_filter.max_pnl_pct is not None:
            filtered = [e for e in filtered if e.net_pnl_pct <= executor_filter.max_pnl_pct]

        # Filter by PnL quote range
        if executor_filter.min_pnl_quote is not None:
            filtered = [e for e in filtered if e.net_pnl_quote >= executor_filter.min_pnl_quote]
        if executor_filter.max_pnl_quote is not None:
            filtered = [e for e in filtered if e.net_pnl_quote <= executor_filter.max_pnl_quote]

        # Filter by timestamp range
        if executor_filter.min_timestamp is not None:
            filtered = [e for e in filtered if e.timestamp >= executor_filter.min_timestamp]
        if executor_filter.max_timestamp is not None:
            filtered = [e for e in filtered if e.timestamp <= executor_filter.max_timestamp]

        # Filter by close timestamp range
        if executor_filter.min_close_timestamp is not None:
            filtered = [e for e in filtered if e.close_timestamp and e.close_timestamp >= executor_filter.min_close_timestamp]
        if executor_filter.max_close_timestamp is not None:
            filtered = [e for e in filtered if e.close_timestamp and e.close_timestamp <= executor_filter.max_close_timestamp]

        return filtered

    def get_executors(self, executor_filter: ExecutorFilter = None) -> List[ExecutorInfo]:
        """
        Get executors with optional filtering.

        :param executor_filter: Optional ExecutorFilter instance
        :return: List of filtered ExecutorInfo objects
        """
        return self.filter_executors(executor_filter=executor_filter)

    def get_active_executors(self,
                             connector_names: Optional[List[str]] = None,
                             trading_pairs: Optional[List[str]] = None,
                             executor_types: Optional[List[str]] = None) -> List[ExecutorInfo]:
        """
        Get all active executors with optional additional filtering.

        :param connector_names: Optional list of connector names to filter by
        :param trading_pairs: Optional list of trading pairs to filter by
        :param executor_types: Optional list of executor types to filter by
        :return: List of active ExecutorInfo objects
        """
        executor_filter = ExecutorFilter(
            is_active=True,
            connector_names=connector_names,
            trading_pairs=trading_pairs,
            executor_types=executor_types
        )
        return self.filter_executors(executor_filter=executor_filter)

    def get_completed_executors(self,
                                connector_names: Optional[List[str]] = None,
                                trading_pairs: Optional[List[str]] = None,
                                executor_types: Optional[List[str]] = None) -> List[ExecutorInfo]:
        """
        Get all completed (terminated) executors with optional additional filtering.

        :param connector_names: Optional list of connector names to filter by
        :param trading_pairs: Optional list of trading pairs to filter by
        :param executor_types: Optional list of executor types to filter by
        :return: List of completed ExecutorInfo objects
        """
        executor_filter = ExecutorFilter(
            statuses=[RunnableStatus.TERMINATED],
            connector_names=connector_names,
            trading_pairs=trading_pairs,
            executor_types=executor_types
        )
        return self.filter_executors(executor_filter=executor_filter)

    def get_executors_by_type(self, executor_types: List[str],
                              connector_names: Optional[List[str]] = None,
                              trading_pairs: Optional[List[str]] = None) -> List[ExecutorInfo]:
        """
        Get executors filtered by type with optional additional filtering.

        :param executor_types: List of executor types to filter by
        :param connector_names: Optional list of connector names to filter by
        :param trading_pairs: Optional list of trading pairs to filter by
        :return: List of filtered ExecutorInfo objects
        """
        executor_filter = ExecutorFilter(
            executor_types=executor_types,
            connector_names=connector_names,
            trading_pairs=trading_pairs
        )
        return self.filter_executors(executor_filter=executor_filter)

    def get_executors_by_side(self, sides: List[TradeType],
                              connector_names: Optional[List[str]] = None,
                              trading_pairs: Optional[List[str]] = None) -> List[ExecutorInfo]:
        """
        Get executors filtered by trading side with optional additional filtering.

        :param sides: List of trading sides (BUY/SELL) to filter by
        :param connector_names: Optional list of connector names to filter by
        :param trading_pairs: Optional list of trading pairs to filter by
        :return: List of filtered ExecutorInfo objects
        """
        executor_filter = ExecutorFilter(
            sides=sides,
            connector_names=connector_names,
            trading_pairs=trading_pairs
        )
        return self.filter_executors(executor_filter=executor_filter)

    async def update_processed_data(self):
        """
        This method should be overridden by the derived classes to implement the logic to update the market data
        used by the controller. And should update the local market data collection to be used by the controller to
        take decisions.
        """
        raise NotImplementedError

    def determine_executor_actions(self) -> List[ExecutorAction]:
        """
        This method should be overridden by the derived classes to implement the logic to determine the actions
        that the executors should take.
        """
        raise NotImplementedError

    def to_format_status(self) -> List[str]:
        """
        This method should be overridden by the derived classes to implement the logic to format the status of the
        controller to be displayed in the UI.
        """
        return []

    def get_custom_info(self) -> dict:
        """
        Override this method to provide custom controller-specific information that will be
        published alongside the performance report via MQTT.

        Note: This data is sent every performance_report_interval (default: 1 second),
        so keep the payload small (recommended: < 1KB) to avoid excessive bandwidth usage.

        Returns:
            dict: Custom information to be included in the MQTT performance report.
                  Empty dict by default.
        """
        return {}

    # Trading API Methods
    def buy(self,
            connector_name: str,
            trading_pair: str,
            amount: Decimal,
            price: Optional[Decimal] = None,
            execution_strategy: ExecutionStrategy = ExecutionStrategy.MARKET,
            chaser_config: Optional[LimitChaserConfig] = None,
            triple_barrier_config: Optional[TripleBarrierConfig] = None,
            leverage: int = 1,
            keep_position: bool = True) -> str:
        """
        Create a buy order using the unified PositionExecutor.

        :param connector_name: Exchange connector name
        :param trading_pair: Trading pair to buy
        :param amount: Amount to buy (in base asset)
        :param price: Price for limit orders (optional for market orders)
        :param execution_strategy: How to execute the order (MARKET, LIMIT, LIMIT_MAKER, LIMIT_CHASER)
        :param chaser_config: Configuration for LIMIT_CHASER strategy
        :param triple_barrier_config: Optional triple barrier configuration for risk management
        :param leverage: Leverage for perpetual trading
        :param keep_position: Whether to keep position after execution (default: True)
        :return: Executor ID for tracking the order
        """
        return self._create_order(
            connector_name=connector_name,
            trading_pair=trading_pair,
            side=TradeType.BUY,
            amount=amount,
            price=price,
            execution_strategy=execution_strategy,
            chaser_config=chaser_config,
            triple_barrier_config=triple_barrier_config,
            leverage=leverage,
            keep_position=keep_position
        )

    def sell(self,
             connector_name: str,
             trading_pair: str,
             amount: Decimal,
             price: Optional[Decimal] = None,
             execution_strategy: ExecutionStrategy = ExecutionStrategy.MARKET,
             chaser_config: Optional[LimitChaserConfig] = None,
             triple_barrier_config: Optional[TripleBarrierConfig] = None,
             leverage: int = 1,
             keep_position: bool = True) -> str:
        """
        Create a sell order using the unified PositionExecutor.

        :param connector_name: Exchange connector name
        :param trading_pair: Trading pair to sell
        :param amount: Amount to sell (in base asset)
        :param price: Price for limit orders (optional for market orders)
        :param execution_strategy: How to execute the order (MARKET, LIMIT, LIMIT_MAKER, LIMIT_CHASER)
        :param chaser_config: Configuration for LIMIT_CHASER strategy
        :param triple_barrier_config: Optional triple barrier configuration for risk management
        :param leverage: Leverage for perpetual trading
        :param keep_position: Whether to keep position after execution (default: True)
        :return: Executor ID for tracking the order
        """
        return self._create_order(
            connector_name=connector_name,
            trading_pair=trading_pair,
            side=TradeType.SELL,
            amount=amount,
            price=price,
            execution_strategy=execution_strategy,
            chaser_config=chaser_config,
            triple_barrier_config=triple_barrier_config,
            leverage=leverage,
            keep_position=keep_position
        )

    def _create_order(self,
                      connector_name: str,
                      trading_pair: str,
                      side: TradeType,
                      amount: Decimal,
                      price: Optional[Decimal] = None,
                      execution_strategy: ExecutionStrategy = ExecutionStrategy.MARKET,
                      chaser_config: Optional[LimitChaserConfig] = None,
                      triple_barrier_config: Optional[TripleBarrierConfig] = None,
                      leverage: int = 1,
                      keep_position: bool = True) -> str:
        """
        Internal method to create orders with the unified PositionExecutor.
        """
        timestamp = self.market_data_provider.time()

        if triple_barrier_config:
            # Create position executor with barriers
            config = PositionExecutorConfig(
                timestamp=timestamp,
                trading_pair=trading_pair,
                connector_name=connector_name,
                side=side,
                amount=amount,
                entry_price=price,
                triple_barrier_config=triple_barrier_config,
                leverage=leverage
            )
        else:
            # Create simple order executor
            config = OrderExecutorConfig(
                timestamp=timestamp,
                trading_pair=trading_pair,
                connector_name=connector_name,
                side=side,
                amount=amount,
                execution_strategy=execution_strategy,
                position_action=PositionAction.OPEN,
                price=price,
                chaser_config=chaser_config,
                leverage=leverage
            )

        # Create executor action
        action = CreateExecutorAction(
            controller_id=self.config.id,
            executor_config=config
        )

        # Add to actions queue for immediate processing
        try:
            self.actions_queue.put_nowait([action])
        except asyncio.QueueFull:
            self.logger().warning("Actions queue is full, cannot place order")
            return ""

        return config.id

    def cancel(self, executor_id: str) -> bool:
        """
        Cancel an active executor (order) by its ID.

        :param executor_id: The ID of the executor to cancel
        :return: True if cancellation request was sent, False otherwise
        """
        # Find the executor
        executor = self._find_executor_by_id(executor_id)
        if executor and executor.is_active:
            action = StopExecutorAction(
                controller_id=self.config.id,
                executor_id=executor_id
            )

            # Add to actions queue
            try:
                self.actions_queue.put_nowait([action])
                return True
            except asyncio.QueueFull:
                self.logger().warning(f"Actions queue is full, cannot cancel executor {executor_id}")
                return False
        else:
            self.logger().warning(f"Executor {executor_id} not found or not active")
            return False

    def cancel_all(self,
                   connector_name: Optional[str] = None,
                   trading_pair: Optional[str] = None,
                   executor_filter: Optional[ExecutorFilter] = None) -> List[str]:
        """
        Cancel all active orders, optionally filtered by connector, trading pair, or advanced filter.

        :param connector_name: Optional connector filter (for backward compatibility)
        :param trading_pair: Optional trading pair filter (for backward compatibility)
        :param executor_filter: Optional ExecutorFilter for advanced filtering
        :return: List of executor IDs that were cancelled
        """
        cancelled_ids = []

        # Use new filtering approach
        if executor_filter:
            # Combine with is_active=True
            filter_with_active = ExecutorFilter(
                is_active=True,
                executor_ids=executor_filter.executor_ids,
                connector_names=executor_filter.connector_names,
                trading_pairs=executor_filter.trading_pairs,
                executor_types=executor_filter.executor_types,
                statuses=executor_filter.statuses,
                sides=executor_filter.sides,
                is_trading=executor_filter.is_trading,
                close_types=executor_filter.close_types,
                controller_ids=executor_filter.controller_ids,
                min_pnl_pct=executor_filter.min_pnl_pct,
                max_pnl_pct=executor_filter.max_pnl_pct,
                min_pnl_quote=executor_filter.min_pnl_quote,
                max_pnl_quote=executor_filter.max_pnl_quote,
                min_timestamp=executor_filter.min_timestamp,
                max_timestamp=executor_filter.max_timestamp,
                min_close_timestamp=executor_filter.min_close_timestamp,
                max_close_timestamp=executor_filter.max_close_timestamp
            )
            executors_to_cancel = self.filter_executors(executor_filter=filter_with_active)
        else:
            # Backward compatibility with basic parameters
            filter_criteria = ExecutorFilter(
                is_active=True,
                connector_names=[connector_name] if connector_name else None,
                trading_pairs=[trading_pair] if trading_pair else None
            )
            executors_to_cancel = self.filter_executors(executor_filter=filter_criteria)

        # Cancel filtered executors
        for executor in executors_to_cancel:
            if self.cancel(executor.id):
                cancelled_ids.append(executor.id)

        return cancelled_ids

    def open_orders(self,
                    connector_name: Optional[str] = None,
                    trading_pair: Optional[str] = None,
                    executor_filter: Optional[ExecutorFilter] = None) -> List[Dict]:
        """
        Get all open orders from active executors.

        :param connector_name: Optional connector filter (for backward compatibility)
        :param trading_pair: Optional trading pair filter (for backward compatibility)
        :param executor_filter: Optional ExecutorFilter for advanced filtering
        :return: List of open order dictionaries
        """
        # Use new filtering approach
        if executor_filter:
            # Combine with is_active=True
            filter_with_active = ExecutorFilter(
                is_active=True,
                executor_ids=executor_filter.executor_ids,
                connector_names=executor_filter.connector_names,
                trading_pairs=executor_filter.trading_pairs,
                executor_types=executor_filter.executor_types,
                statuses=executor_filter.statuses,
                sides=executor_filter.sides,
                is_trading=executor_filter.is_trading,
                close_types=executor_filter.close_types,
                controller_ids=executor_filter.controller_ids,
                min_pnl_pct=executor_filter.min_pnl_pct,
                max_pnl_pct=executor_filter.max_pnl_pct,
                min_pnl_quote=executor_filter.min_pnl_quote,
                max_pnl_quote=executor_filter.max_pnl_quote,
                min_timestamp=executor_filter.min_timestamp,
                max_timestamp=executor_filter.max_timestamp,
                min_close_timestamp=executor_filter.min_close_timestamp,
                max_close_timestamp=executor_filter.max_close_timestamp
            )
            filtered_executors = self.filter_executors(executor_filter=filter_with_active)
        else:
            # Backward compatibility with basic parameters
            filter_criteria = ExecutorFilter(
                is_active=True,
                connector_names=[connector_name] if connector_name else None,
                trading_pairs=[trading_pair] if trading_pair else None
            )
            filtered_executors = self.filter_executors(executor_filter=filter_criteria)

        # Convert to order info dictionaries
        open_orders = []
        for executor in filtered_executors:
            order_info = {
                'executor_id': executor.id,
                'connector_name': executor.connector_name,
                'trading_pair': executor.trading_pair,
                'side': executor.side,
                'amount': executor.config.amount if hasattr(executor.config, 'amount') else None,
                'filled_amount': executor.filled_amount_quote,
                'status': executor.status.value,
                'net_pnl_pct': executor.net_pnl_pct,
                'net_pnl_quote': executor.net_pnl_quote,
                'order_ids': executor.custom_info.get('order_ids', []),
                'type': executor.type,
                'timestamp': executor.timestamp,
                'is_trading': executor.is_trading
            }
            open_orders.append(order_info)

        return open_orders

    def open_positions(self,
                       connector_name: Optional[str] = None,
                       trading_pair: Optional[str] = None,
                       executor_filter: Optional[ExecutorFilter] = None) -> List[Dict]:
        """
        Get all held positions from completed executors.

        :param connector_name: Optional connector filter (for backward compatibility)
        :param trading_pair: Optional trading pair filter (for backward compatibility)
        :param executor_filter: Optional ExecutorFilter for advanced filtering
        :return: List of position dictionaries
        """
        # Filter positions_held directly since it's a separate list
        held_positions = []

        for position in self.positions_held:
            should_include = True

            # Apply basic filters for backward compatibility
            if connector_name and position.connector_name != connector_name:
                should_include = False

            if trading_pair and position.trading_pair != trading_pair:
                should_include = False

            # Apply advanced filter if provided
            if executor_filter and should_include:
                # Check connector names
                if executor_filter.connector_names and position.connector_name not in executor_filter.connector_names:
                    should_include = False

                # Check trading pairs
                if executor_filter.trading_pairs and position.trading_pair not in executor_filter.trading_pairs:
                    should_include = False

                # Check sides
                if executor_filter.sides and position.side not in executor_filter.sides:
                    should_include = False

                # Check PnL ranges
                if executor_filter.min_pnl_pct is not None and position.pnl_percentage < executor_filter.min_pnl_pct:
                    should_include = False

                if executor_filter.max_pnl_pct is not None and position.pnl_percentage > executor_filter.max_pnl_pct:
                    should_include = False

                if executor_filter.min_pnl_quote is not None and position.pnl_quote < executor_filter.min_pnl_quote:
                    should_include = False

                if executor_filter.max_pnl_quote is not None and position.pnl_quote > executor_filter.max_pnl_quote:
                    should_include = False

                # Check timestamp ranges
                if executor_filter.min_timestamp is not None and position.timestamp < executor_filter.min_timestamp:
                    should_include = False

                if executor_filter.max_timestamp is not None and position.timestamp > executor_filter.max_timestamp:
                    should_include = False

            if should_include:
                position_info = {
                    'connector_name': position.connector_name,
                    'trading_pair': position.trading_pair,
                    'side': position.side,
                    'amount': position.amount,
                    'entry_price': position.entry_price,
                    'current_price': position.current_price,
                    'pnl_percentage': position.pnl_percentage,
                    'pnl_quote': position.pnl_quote,
                    'timestamp': position.timestamp
                }
                held_positions.append(position_info)

        return held_positions

    def get_current_price(self, connector_name: str, trading_pair: str, price_type: PriceType = PriceType.MidPrice) -> Decimal:
        """
        Get current market price for a trading pair.

        :param connector_name: Exchange connector name
        :param trading_pair: Trading pair
        :param price_type: Type of price to retrieve (MidPrice, BestBid, BestAsk)
        :return: Current price
        """
        return self.market_data_provider.get_price_by_type(connector_name, trading_pair, price_type)

    def _find_executor_by_id(self, executor_id: str) -> Optional[ExecutorInfo]:
        """
        Find an executor by its ID.

        :param executor_id: The executor ID to find
        :return: ExecutorInfo if found, None otherwise
        """
        for executor in self.executors_info:
            if executor.id == executor_id:
                return executor
        return None
