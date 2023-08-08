from typing import Generic, TypeVar

from pydantic import BaseModel

from hummingbot.smart_components.meta_strategies.data_types import MetaStrategyMode
from hummingbot.smart_components.meta_strategies.market_making.market_making_strategy_base import OrderLevel

ConfigType = TypeVar("ConfigType", bound=BaseModel)


class MetaStrategyBase(Generic[ConfigType]):
    def __init__(self, config: ConfigType, mode: MetaStrategyMode = MetaStrategyMode.LIVE):
        self.config = config
        self.mode = mode

    def get_csv_prefix(self) -> str:
        raise f"{self.config.strategy_name}"

    def get_order_levels(self) -> list[OrderLevel]:
        raise NotImplementedError
