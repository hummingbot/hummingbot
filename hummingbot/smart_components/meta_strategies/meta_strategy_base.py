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
        return f"{self.config.strategy_name}"

    def to_format_status(self):
        lines = []
        lines.extend(["\n################################ Meta Strategy Config ################################"])
        lines.extend(["Config:\n"])
        for parameter, value in self.config.dict().items():
            if parameter not in ["order_levels", "candles_config"]:
                lines.extend([f"     {parameter}: {value}"])
        return lines
