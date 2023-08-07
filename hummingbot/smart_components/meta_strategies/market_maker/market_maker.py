import asyncio
from enum import Enum

from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.smart_components.smart_component_base import SmartComponentStatus
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class MetaStrategyStatus(Enum):
    NOT_STARTED = 1
    ACTIVE = 2
    TERMINATED = 3


class MarketMakerStrategy:
    def __init__(self):
        self.levels = self._get_order_levels()


class MarketMaker:
    def __init__(self, strategy: ScriptStrategyBase, market_making_strategy: MarketMakerStrategy, update_interval: float = 1):
        self.strategy = strategy
        self.mms = market_making_strategy
        self.update_interval = update_interval
        self.terminated = asyncio.Event()
        self._current_levels = {level.id: None for level in self._strategy.levels}

    def start(self):
        safe_ensure_future(self.control_loop())

    def on_stop(self):
        pass

    def on_start(self):
        pass

    async def control_task(self):
        for order_level in self.mms.levels:
            current_executor = self._current_levels[order_level.id]
            if current_executor and current_executor.status == SmartComponentStatus.ACTIVE:
                if self.mms.refresh_order_condition(current_executor, order_level) or self.mms.early_stop_condition(current_executor):
                    current_executor.early_stop()
            else:
                pass

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
