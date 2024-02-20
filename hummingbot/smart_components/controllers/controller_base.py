import asyncio
import hashlib
import random
import time
from typing import List

import base58
from pydantic import BaseModel, validator

from hummingbot.core.data_type.common import PositionMode
from hummingbot.core.event.events import ExecutorEvent
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.data_feed.market_data_provider import MarketDataProvider
from hummingbot.smart_components.models.executors_info import ExecutorInfo
from hummingbot.smart_components.smart_component_base import SmartComponentBase
from hummingbot.strategy.strategy_v2_base import V2StrategyBase


class ControllerConfigBase(BaseModel):
    id: str = None
    strategy_name: str
    candles_config: List[CandlesConfig]
    position_mode: PositionMode = PositionMode.HEDGE
    leverage: int = 1

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
        # Subscribe to executor updates
        V2StrategyBase.pubsub.add_listener(ExecutorEvent.EXECUTOR_INFO_UPDATE, self.handle_executor_update)
        # Initialize candles in the market data provider
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
        """
        The main control task of the controller.
        """
        raise NotImplementedError
