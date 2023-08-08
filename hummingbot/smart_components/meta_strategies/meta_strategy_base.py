from typing import Generic, TypeVar

from pydantic import BaseModel

from hummingbot.smart_components.meta_strategies.data_types import MetaStrategyMode

ConfigType = TypeVar("ConfigType", bound=BaseModel)


class MetaStrategyBase(Generic[ConfigType]):
    def __init__(self, config: ConfigType, mode: MetaStrategyMode = MetaStrategyMode.LIVE):
        self.config = config
        self.mode = mode

    def start(self):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def get_csv_prefix(self) -> str:
        raise f"{self.config.strategy_name}"
