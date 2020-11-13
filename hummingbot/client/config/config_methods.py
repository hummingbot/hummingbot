from hummingbot.client.config.config_var import ConfigVar
from typing import Callable


def new_fee_config_var(key):
    return ConfigVar(key=key,
                     prompt=None,
                     required_if=lambda: False,
                     type_str="decimal")


def paper_trade_disabled():
    from hummingbot.client.config.global_config_map import global_config_map
    return global_config_map.get("paper_trade_enabled").value is False


def using_exchange(exchange: str) -> Callable:
    from hummingbot.client.settings import required_exchanges
    return lambda: paper_trade_disabled() and exchange in required_exchanges
