from enum import Enum

from hummingbot.smart_components.meta_strategies.market_making.market_making_strategy_base import (
    MarketMakingStrategyBase,
)
from hummingbot.smart_components.meta_strategies.meta_executor_base import MetaExecutorBase
from hummingbot.smart_components.smart_component_base import SmartComponentStatus
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class MetaStrategyStatus(Enum):
    NOT_STARTED = 1
    ACTIVE = 2
    TERMINATED = 3


class MetaStrategyMode(Enum):
    BACKTEST = 1
    LIVE = 2


class MarketMaker(MetaExecutorBase):
    def __init__(self, strategy: ScriptStrategyBase, meta_strategy: MarketMakingStrategyBase, update_interval: float = 1.0):
        super().__init__(strategy, meta_strategy, update_interval)
        self.ms = meta_strategy

    async def control_task(self):
        for order_level in self.ms.config.order_levels:
            current_executor = self.level_executors[order_level.level_id]
            if current_executor and current_executor.status == SmartComponentStatus.ACTIVE:
                if self.ms.refresh_order_condition(current_executor, order_level) or \
                        self.ms.early_stop_condition(current_executor):
                    current_executor.early_stop()
            else:
                if not self.ms.cooldown_condition(current_executor):
                    self.store_executor(current_executor, order_level.level_id)
                    position_config = self.ms.get_position_config(order_level)
                    self.create_executor(position_config, order_level.level_id)
