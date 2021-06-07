from typing import (
    Optional,
)

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_market_trading_pair
)
from hummingbot.client.settings import (
    required_exchanges,
    EXAMPLE_ASSETS,
    EXAMPLE_PAIRS,
)


def exchange_on_validated(value: str) -> None:
    required_exchanges.append(value)


def trading_pair_prompt():
    exchange = dev_0_hello_world_config_map.get("exchange").value
    example = EXAMPLE_PAIRS.get(exchange)
    return "Enter the trading pair you would like to trade on %s%s >>> " \
           % (exchange, f" (e.g. {example})" if example else "")


def asset_prompt():
    trading_pair = dev_0_hello_world_config_map.get("trading_pair").value
    example = EXAMPLE_ASSETS.get(trading_pair)
    return "Enter a single token to fetch its balance on %s%s >>> " \
           % (trading_pair, f" (e.g. {example})" if example else "")


def validate_exchange_trading_pair(value: str) -> Optional[str]:
    exchange = dev_0_hello_world_config_map.get("exchange").value
    return validate_market_trading_pair(exchange, value)


dev_0_hello_world_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="dev_0_hello_world",
                  ),
    "exchange":
        ConfigVar(key="exchange",
                  prompt="Enter the name of the exchange >>> ",
                  validator=validate_exchange,
                  on_validated=exchange_on_validated,
                  prompt_on_new=True,
                  ),
    "trading_pair":
        ConfigVar(key="trading_pair",
                  prompt=trading_pair_prompt,
                  validator=validate_exchange_trading_pair,
                  type_str="str",
                  prompt_on_new=True,
                  ),
    "asset":
        ConfigVar(key="asset",
                  prompt=asset_prompt,
                  type_str="str",
                  prompt_on_new=True,
                  ),
}
