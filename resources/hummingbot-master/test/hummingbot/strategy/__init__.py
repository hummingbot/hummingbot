from typing import Dict
from hummingbot.client.config.config_var import ConfigVar


def assign_config_default(config_map: Dict[str, ConfigVar]):
    for key, value in config_map.items():
        value.value = value.default
