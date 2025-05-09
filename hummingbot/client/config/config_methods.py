from typing import Callable

from hummingbot.client.config.config_var import ConfigVar


def new_fee_config_var(key: str, type_str: str = "decimal"):
    return ConfigVar(key=key,
                     prompt=None,
                     required_if=lambda: False,
                     type_str=type_str)


def using_exchange(exchange: str) -> Callable:
    from hummingbot.client.settings import required_exchanges
    return lambda: exchange in required_exchanges
