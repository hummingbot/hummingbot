import asyncio
import importlib
import inspect
from decimal import Decimal
from typing import TYPE_CHECKING, Callable, List

from pydantic import ConfigDict, Field, field_validator

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.core.data_type.common import MarketDict
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.data_feed.market_data_provider import MarketDataProvider
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executor_actions import ExecutorAction
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo
from hummingbot.strategy_v2.models.position_config import InitialPositionConfig
from hummingbot.strategy_v2.runnable_base import RunnableBase
from hummingbot.strategy_v2.utils.common import generate_unique_id

if TYPE_CHECKING:
    from hummingbot.strategy_v2.executors.data_types import PositionSummary


class ControllerConfigBase(BaseClientModel):
    """
    This class represents the base configuration for a controller in the Hummingbot trading bot.
    It inherits from the Pydantic BaseModel and includes several fields that are used to configure a controller.

    Attributes:
        id (str): A unique identifier for the controller. If not provided, it will be automatically generated.
        controller_name (str): The name of the trading strategy that the controller will use.
        candles_config (List[CandlesConfig]): A list of configurations for the candles data feed.
    """
    id: str = Field(default=None,)
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
    candles_config: List[CandlesConfig] = Field(
        default=[],
        json_schema_extra={"is_updatable": True})
    initial_positions: List[InitialPositionConfig] = Field(
        default=[],
        json_schema_extra={
            "prompt": "Enter initial positions as a list of InitialPositionConfig objects: ",
            "prompt_on_new": False,
            "is_updatable": False
        })
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator('id', mode="before")
    @classmethod
    def set_id(cls, v):
        if v is None or v.strip() == "":
            return generate_unique_id()
        return v

    @field_validator('candles_config', mode="before")
    @classmethod
    def parse_candles_config(cls, v) -> List[CandlesConfig]:
        if isinstance(v, str):
            return cls.parse_candles_config_str(v)
        elif isinstance(v, list):
            return v
        raise ValueError("Invalid type for candles_config. Expected str or List[CandlesConfig]")

    @field_validator('initial_positions', mode="before")
    @classmethod
    def parse_initial_positions(cls, v) -> List[InitialPositionConfig]:
        if isinstance(v, list):
            return v
        raise ValueError("Invalid type for initial_positions. Expected List[InitialPositionConfig]")

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

    def update_markets(self, markets: MarketDict) -> MarketDict:
        """
        Update the markets dict of the script from the config.
        """
        return markets

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
    """

    def __init__(self, config: ControllerConfigBase, market_data_provider: MarketDataProvider,
                 actions_queue: asyncio.Queue, update_interval: float = 1.0):
        super().__init__(update_interval=update_interval)
        self.config = config
        self.executors_info: List[ExecutorInfo] = []
        self.positions_held: List[PositionSummary] = []
        self.market_data_provider: MarketDataProvider = market_data_provider
        self.actions_queue: asyncio.Queue = actions_queue
        self.processed_data = {}
        self.executors_update_event = asyncio.Event()
        self.executors_info_queue = asyncio.Queue()

    def start(self):
        """
        Allow controllers to be restarted after being stopped.=
        """
        if self._status != RunnableStatus.RUNNING:
            self.terminated.clear()
            self._status = RunnableStatus.RUNNING
            self.executors_update_event.set()
            safe_ensure_future(self.control_loop())
        self.initialize_candles()

    def initialize_candles(self):
        for candles_config in self.config.candles_config:
            self.market_data_provider.initialize_candles_feed(candles_config)

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

    @staticmethod
    def filter_executors(executors: List[ExecutorInfo], filter_func: Callable[[ExecutorInfo], bool]) -> List[ExecutorInfo]:
        return [executor for executor in executors if filter_func(executor)]

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
