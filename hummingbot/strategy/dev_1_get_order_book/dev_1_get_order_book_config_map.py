from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_market_trading_pair,
)
from hummingbot.client.settings import (
    required_exchanges,
    EXAMPLE_PAIRS,
)
from typing import Optional


def trading_pair_prompt():
    market = dev_1_get_order_book_config_map.get("market").value
    example = EXAMPLE_PAIRS.get(market)
    return "Enter the token trading pair to fetch its order book on %s%s >>> " \
           % (market, f" (e.g. {example})" if example else "")


def str2bool(value: str):
    return str(value).lower() in ("yes", "true", "t", "1")


# checks if the trading pair is valid
def validate_trading_pair(value: str) -> Optional[str]:
    market = dev_1_get_order_book_config_map.get("market").value
    return validate_market_trading_pair(market, value)


dev_1_get_order_book_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="dev_1_get_order_book"),
    "market":
        ConfigVar(key="market",
                  prompt="Enter the name of the exchange >>> ",
                  validator=validate_exchange,
                  on_validated=lambda value: required_exchanges.append(value)),
    "market_trading_pair":
        ConfigVar(key="market_trading_pair",
                  prompt=trading_pair_prompt,
                  validator=validate_trading_pair),
}
