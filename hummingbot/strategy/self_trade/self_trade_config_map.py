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
    market = self_trade_config_map.get("market").value
    example = EXAMPLE_PAIRS.get(market)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (market, f" (e.g. {example})" if example else "")


def str2bool(value: str):
    return str(value).lower() in ("yes", "true", "t", "1")


# checks if the trading pair is valid
def validate_market_trading_pair_tuple(value: str) -> Optional[str]:
    market = self_trade_config_map.get("market").value
    return validate_market_trading_pair(market, value)


self_trade_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="self_trade"),
    "market":
        ConfigVar(key="market",
                  prompt="Enter the name of the exchange >>> ",
                  validator=validate_exchange,
                  on_validated=lambda value: required_exchanges.append(value)),
    "market_trading_pair_tuple":
        ConfigVar(key="market_trading_pair_tuple",
                  prompt=trading_pair_prompt,
                  validator=validate_market_trading_pair_tuple),
    "min_order_amount":
        ConfigVar(key="min_order_amount",
                  prompt="What is your preferred min quantity per order (denominated in the base asset, default is 1)? "
                         ">>> ",
                  default=1.0,
                  type_str="decimal"),
    "max_order_amount":
        ConfigVar(key="max_order_amount",
                  prompt="What is your preferred max quantity per order (denominated in the base asset, default is 1)? "
                         ">>> ",
                  default=2.0,
                  type_str="decimal"),
    "time_delay":
        ConfigVar(key="time_delay",
                  prompt="How much do you want to wait to place the order (Enter 10 to indicate 10 seconds. "
                         "Default is 0)? >>> ",
                  type_str="float",
                  default=0),
    "cancel_order_wait_time":
        ConfigVar(key="cancel_order_wait_time",
                  prompt="How long do you want to wait before cancelling your limit order (in seconds). "
                         "(Default is 60 seconds) ? >>> ",
                  required_if=lambda: True,
                  type_str="float",
                  default=60),
    "percentage_of_price_change":
        ConfigVar(key="percentage_of_price_change",
                  prompt="By what percentage to change the price when placing orders (in percentage). "
                         "(Default is 0 percentage) ? >>> ",
                  type_str="float",
                  default=0),
    "trade_bands":
        ConfigVar(key="trade_bands",
                  prompt="restrictions on the trading volume in the timestamp (hours: amount) ? >>> ",
                  type_str="str",
                  default=""),
    "delta_price_changed_percent":
        ConfigVar(key="price_changed_percent",
                  prompt="the percentage by which the price will change (in percentage) ? >>> ",
                  type_str="decimal",
                  default="0.0"),
}
