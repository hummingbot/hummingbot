from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
)
from hummingbot.client.settings import (
    required_exchanges,
    EXAMPLE_ASSETS,
)


def trading_pair_prompt():
    market = dev_0_hello_world_config_map.get("market").value
    example = EXAMPLE_ASSETS.get(market)
    return "Enter a single token to fetch its balance on %s%s >>> " \
           % (market, f" (e.g. {example})" if example else "")


def str2bool(value: str):
    return str(value).lower() in ("yes", "true", "t", "1")


dev_0_hello_world_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="dev_0_hello_world"),
    "market":
        ConfigVar(key="market",
                  prompt="Enter the name of the exchange >>> ",
                  validator=validate_exchange,
                  on_validated=lambda value: required_exchanges.append(value)),
    "asset_trading_pair":
        ConfigVar(key="asset_trading_pair",
                  prompt=trading_pair_prompt),
}
