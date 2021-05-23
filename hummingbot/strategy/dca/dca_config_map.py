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
    market = dca_config_map.get("market").value
    example = EXAMPLE_PAIRS.get(market)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (market, f" (e.g. {example})" if example else "")



# checks if the trading pair is valid
def validate_market_trading_pair_tuple(value: str) -> Optional[str]:
    market = dca_config_map.get("market").value
    return validate_market_trading_pair(market, value)


dca_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="dca"),
    "market":
        ConfigVar(key="market",
                  prompt="Enter the name of the exchange >>> ",
                  validator=validate_exchange,
                  on_validated=lambda value: required_exchanges.append(value)),

    "market_trading_pair_tuple":
        ConfigVar(key="market_trading_pair_tuple",
                  prompt=trading_pair_prompt,
                  validator=validate_market_trading_pair_tuple),
    "order_amount":
        ConfigVar(key="order_amount",
                  prompt="What is your preferred quantity (denominated in the base asset, default is 1)? "
                         ">>> ",
                  default=1.0,
                  type_str="float"),
    "num_individual_orders":
        ConfigVar(key="num_individual_orders",
                  prompt="Into how many times do you want to place order? (Enter 10 to indicate 10 individual orders. "
                         "Default is 6)? >>> ",
                  type_str="int",
                  default=6),
    "days_period":
        ConfigVar(key="days_period",
                  prompt="How many days do you want to wait between each individual order? (Enter 30 to indicate 30 days. "
                         "Default is 30)? >>> ",
                  type_str="int",
                  default=30),
}
