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
    market = stones_with_payback_config_map.get("market").value
    example = EXAMPLE_PAIRS.get(market)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (market, f" (e.g. {example})" if example else "")


def str2bool(value: str):
    return str(value).lower() in ("yes", "true", "t", "1")


# checks if the trading pair is valid
def validate_market_trading_pair_tuple(value: str) -> Optional[str]:
    market = stones_with_payback_config_map.get("market").value
    errors = []
    for pair in value[1:-2].replace("'", "").split(','):
        error_msg = validate_market_trading_pair(market, pair.strip())
        if error_msg is not None:
            errors.append(error_msg)
    return None if len(errors) == 0 else "; ".join(list(errors))


# checks if the trading pair is valid
def validate_payback_market_trading_pair_tuple(value: str) -> Optional[str]:
    market = stones_with_payback_config_map.get("payback_market").value
    errors = []
    v = value[13:-2].replace("'", "").replace("(", "").split('),')
    v = map(lambda x: x.replace(')', '').split(', '), v)
    v = list(map(lambda x: x[1], filter(lambda y: len(y) == 2, v)))
    for pair in v:
        error_msg = validate_market_trading_pair(market, pair.strip())
        if error_msg is not None:
            errors.append(error_msg)
    return None if len(errors) == 0 else "; ".join(list(errors))


stones_with_payback_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="stones_with_payback"),
    "market":
        ConfigVar(key="market",
                  prompt="Enter the name of the exchange >>> ",
                  validator=validate_exchange,
                  on_validated=lambda value: required_exchanges.append(value)),
    "payback_market":
        ConfigVar(key="payback_market",
                  prompt="Enter the name of the payback exchange >>> ",
                  validator=validate_exchange,
                  on_validated=lambda value: required_exchanges.append(value)),
    "market_trading_pair_tuple":
        ConfigVar(key="market_trading_pair_tuple",
                  prompt=trading_pair_prompt,
                  validator=validate_market_trading_pair_tuple,
                  type_str="list"),
    "payback_info":
        ConfigVar(key="payback_info",
                  prompt="",
                  required_if=lambda: False,
                  validator=validate_payback_market_trading_pair_tuple,
                  default={},
                  type_str="json"),
    "total_buy_order_amount":
        ConfigVar(key="total_buy_order_amount",
                  prompt="The sum (at a specific time) of all buy orders in the depth (denominated in the base asset)? >>> ",
                  required_if=lambda: True,
                  type_str="json"),
    "total_sell_order_amount":
        ConfigVar(key="total_sell_order_amount",
                  prompt="The sum (at a specific time) of all sell orders in the depth (denominated in the base asset)? >>> ",
                  required_if=lambda: True,
                  type_str="json"),
    "time_delay":
        ConfigVar(key="time_delay",
                  prompt="How much do you want to wait to place the order (Enter 10 to indicate 10 seconds. Default is 0)? >>> ",
                  type_str="float",
                  default=0),
    "buy_order_levels":
        ConfigVar(key="buy_order_levels",
                  prompt="rRules for the buy order levels ? >>> ",
                  type_str="json",
                  default="{}"),
    "sell_order_levels":
        ConfigVar(key="sell_order_levels",
                  prompt="Rules for the sell order levels ? >>> ",
                  type_str="json",
                  default="{}"),
}
