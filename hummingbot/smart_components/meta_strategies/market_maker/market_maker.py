import asyncio
import datetime
import os
from enum import Enum
from typing import List, Optional

import pandas as pd
from pydantic import BaseModel

from hummingbot import data_path
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig, CandlesFactory
from hummingbot.smart_components.executors.position_executor.data_types import PositionConfig
from hummingbot.smart_components.executors.position_executor.position_executor import PositionExecutor
from hummingbot.smart_components.smart_component_base import SmartComponentStatus
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class MetaStrategyStatus(Enum):
    NOT_STARTED = 1
    ACTIVE = 2
    TERMINATED = 3


class MetaStrategyMode(Enum):
    BACKTEST = 1
    LIVE = 2


class OrderLevel(BaseModel):
    level: int
    side: str
    order_amount_usd: float
    spread_factor: float
    # Configure the parameters for the position
    stop_loss: Optional[float]
    take_profit: Optional[float]
    time_limit: Optional[int]
    trailing_stop_activation_delta: Optional[float]
    trailing_stop_trailing_delta: Optional[float]
    # Configure the parameters for the order
    open_order_type: OrderType = OrderType.LIMIT
    take_profit_order_type: OrderType = OrderType.MARKET
    stop_loss_order_type: OrderType = OrderType.MARKET
    time_limit_order_type: OrderType = OrderType.MARKET

    def __post_init__(self):
        self.level_id = f"{self.side}_{self.level}"


class MarketMakerConfig(BaseModel):
    exchange: str
    trading_pair: str
    order_refresh_time: int = 60
    cooldown_time: int = 0
    order_levels: List[OrderLevel]


class MarketMakerStrategyBase:
    def __init__(self, candles_config: List[CandlesConfig], mode: MetaStrategyMode = MetaStrategyMode.LIVE):
        self.mode = mode
        self.candles = self.initialize_candles(candles_config)
        self.levels = self.get_order_levels()

    def initialize_candles(self, candles_config: List[CandlesConfig]):
        if self.mode == MetaStrategyMode.LIVE:
            return [CandlesFactory.get_candle(candles_config) for candles_config in candles_config]
        else:
            raise NotImplementedError

    def start(self):
        for candle in self.candles:
            candle.start()

    @property
    def is_perpetual(self):
        """
        Checks if the exchange is a perpetual market.
        """
        return "perpetual" in self.exchange

    @property
    def all_candles_ready(self):
        """
        Checks if the candlesticks are full.
        """
        return all([candle.is_ready for candle in self.candles])

    def get_order_levels(self) -> List[OrderLevel]:
        raise NotImplementedError

    def refresh_order_condition(self, executor: PositionExecutor, order_level: OrderLevel) -> bool:
        raise NotImplementedError

    def early_stop_condition(self, executor: PositionExecutor) -> bool:
        raise NotImplementedError

    def cooldown_condition(self, executor: PositionExecutor) -> bool:
        raise NotImplementedError

    def get_position_config(self, order_level: OrderLevel) -> PositionConfig:
        raise NotImplementedError


class MarketMaker:
    def __init__(self, strategy: ScriptStrategyBase, market_making_strategy: MarketMakerStrategyBase, update_interval: float = 1):
        self.strategy = strategy
        self.mms = market_making_strategy
        self.update_interval = update_interval
        self.terminated = asyncio.Event()
        self._current_levels = {level.level_id: None for level in self.mms.levels}

    def start(self):
        safe_ensure_future(self.control_loop())

    def on_stop(self):
        pass

    def on_start(self):
        self.mms.start()

    async def control_task(self):
        for order_level in self.mms.levels:
            current_executor = self._current_levels[order_level.level_id]
            if current_executor and current_executor.status == SmartComponentStatus.ACTIVE:
                if self.mms.refresh_order_condition(current_executor, order_level) or \
                        self.mms.early_stop_condition(current_executor):
                    current_executor.early_stop()
            else:
                if not self.mms.cooldown_condition(current_executor):
                    self.store_executor(current_executor, order_level.level_id)
                    position_config = self.mms.get_position_config(order_level)
                    self.create_executor(position_config, order_level.level_id)

    def get_csv_path(self) -> str:
        today = datetime.datetime.today()
        csv_path = data_path() + f"/{self.mms.strategy_name}_position_executors_{self.mms.exchange}_" \
                                 f"{self.mms.trading_pair}_{today.day:02d}-{today.month:02d}-{today.year}.csv"
        return csv_path

    def store_executor(self, executor: PositionExecutor, order_level: str):
        if executor:
            csv_path = self.get_csv_path()
            executor_data = executor.to_json()
            if not os.path.exists(csv_path):
                headers = executor_data.keys()
                df_header = pd.DataFrame(columns=headers)
                df_header.to_csv(csv_path, mode='a', header=True, index=False)
            df = pd.DataFrame([executor_data])
            df.to_csv(csv_path, mode='a', header=False, index=False)
            self._current_levels[order_level] = None

    def create_executor(self, position_config: PositionConfig, order_level: str):
        executor = PositionExecutor(self.strategy, position_config)
        self._current_levels[order_level] = executor

    async def control_loop(self):
        self.on_start()
        self._status = MetaStrategyStatus.ACTIVE
        while not self.terminated.is_set():
            await self.control_task()
            await asyncio.sleep(self.update_interval)
        self._status = MetaStrategyStatus.TERMINATED
        self.on_stop()

    def terminate_control_loop(self):
        self.terminated.set()
