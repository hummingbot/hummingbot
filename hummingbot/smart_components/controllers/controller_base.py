import asyncio
import hashlib
import random
import time
from typing import Callable, List

import base58
from pydantic import Field, validator

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.data_feed.market_data_provider import MarketDataProvider
from hummingbot.smart_components.models.executor_actions import ExecutorAction
from hummingbot.smart_components.models.executors_info import ExecutorInfo
from hummingbot.smart_components.smart_component_base import SmartComponentBase


class ControllerConfigBase(BaseClientModel):
    """
    This class represents the base configuration for a controller in the Hummingbot trading bot.
    It inherits from the Pydantic BaseModel and includes several fields that are used to configure a controller.

    Attributes:
        id (str): A unique identifier for the controller. If not provided, it will be automatically generated.
        controller_name (str): The name of the trading strategy that the controller will use.
        candles_config (List[CandlesConfig]): A list of configurations for the candles data feed.
    """
    id: str = None
    controller_name: str
    candles_config: List[CandlesConfig] = Field(
        default="binance_perpetual.WLD-USDT.1m.500",
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: (
                "Enter candle configs in format 'exchange1.tp1.interval1.max_records:"
                "exchange2.tp2.interval2.max_records':"
            )
        )
    )

    @validator('candles_config', pre=True)
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

    @validator('id', pre=True, always=True)
    def set_id(cls, v, values):
        if v is None:
            # Use timestamp from values if available, else current time
            timestamp = values.get('timestamp', time.time())
            unique_component = random.randint(0, 99999)
            raw_id = f"{timestamp}-{unique_component}"
            hashed_id = hashlib.sha256(raw_id.encode()).digest()  # Get bytes
            return base58.b58encode(hashed_id).decode()  # Base58 encode
        return v


class ControllerBase(SmartComponentBase):
    """
    Base class for controllers.
    """
    def __init__(self, config: ControllerConfigBase, market_data_provider: MarketDataProvider,
                 actions_queue: asyncio.Queue, update_interval: float = 1.0):
        super().__init__(update_interval=update_interval)
        self.config = config
        self.executors_info: List[ExecutorInfo] = []
        self.market_data_provider: MarketDataProvider = market_data_provider
        self.actions_queue: asyncio.Queue = actions_queue
        self.processed_data = {}
        self.initialize_candles()

    async def handle_executor_update(self, executors_info):
        """
        Handle executors updates, by default we are going to store the executors related to this controller, but
        this method can be overridden to implement custom behavior.
        """
        self.executors_info = executors_info.get(self.config.id, [])

    def initialize_candles(self):
        for candles_config in self.config.candles_config:
            self.market_data_provider.initialize_candles_feed(candles_config)

    async def control_task(self):
        if self.market_data_provider.ready:
            await self.update_market_data()
            executor_actions: List[ExecutorAction] = self.determine_executor_actions()
            for action in executor_actions:
                await self.actions_queue.put(action)

    @staticmethod
    def filter_executors(executors: List[ExecutorInfo], filter_func: Callable[[ExecutorInfo], bool]) -> List[ExecutorInfo]:
        return [executor for executor in executors if filter_func(executor)]

    async def update_market_data(self):
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
