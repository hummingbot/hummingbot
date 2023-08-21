from typing import TypeVar

from pydantic import BaseModel

from hummingbot.smart_components.data_types import ControllerMode

ConfigType = TypeVar("ConfigType", bound=BaseModel)


class ControllerBase:
    def __init__(self, config: ConfigType, mode: ControllerMode = ControllerMode.LIVE):
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
        lines.extend(["\n################################ Controller Config ################################"])
        lines.extend(["Config:\n"])
        for parameter, value in self.config.dict().items():
            if parameter not in ["order_levels", "candles_config"]:
                lines.extend([f"     {parameter}: {value}"])
        return lines
