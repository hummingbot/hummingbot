from hummingbot.client.config.config_var import ConfigVar
from typing import Callable


def new_fee_config_var(key: str, type_str: str = "decimal"):
    return ConfigVar(key=key,
                     prompt=None,
                     required_if=lambda: False,
                     type_str=type_str)


def using_exchange(exchange: str) -> Callable:
    from hummingbot.client.settings import required_exchanges
    return lambda: exchange in required_exchanges
