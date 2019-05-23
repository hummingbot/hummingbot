from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    is_exchange,
    is_valid_market_symbol,
)
from hummingbot.client.settings import (
    required_exchanges,
    EXAMPLE_PAIRS,
)


def maker_symbol_prompt():
    maker_market = pure_market_making_config_map.get("maker_market").value
    example = EXAMPLE_PAIRS.get(maker_market)
    return "Enter the token symbol you would like to trade on %s%s >>> " \
           % (maker_market, f" (e.g. {example})" if example else "")


# strategy specific validators
def is_valid_maker_market_symbol(value: str) -> bool:
    maker_market = pure_market_making_config_map.get("maker_market").value
    return is_valid_market_symbol(maker_market, value)


pure_market_making_config_map = {
    "maker_market":                     ConfigVar(key="maker_market",
                                                  prompt="Enter your maker exchange name >>> ",
                                                  validator=is_exchange,
                                                  on_validated=lambda value: required_exchanges.append(value)),
    "maker_market_symbol":              ConfigVar(key="primary_market_symbol",
                                                  prompt=maker_symbol_prompt,
                                                  validator=is_valid_maker_market_symbol),
    "order_amount":                     ConfigVar(key="order_amount",
                                                  prompt="What is your preferred quantity per order (denominated in "
                                                         "the base asset, default is 1)? >>> ",
                                                  default=1.0,
                                                  type_str="float"),
    "bid_place_threshold":              ConfigVar(key="bid_place_threshold",
                                                  prompt="How far away from the mid price do you want to place the next bid"
                                                         "(Enter 0.01 to indicate 1%)? >>> ",
                                                  type_str="float",
                                                  default=0.01),
    "ask_place_threshold":              ConfigVar(key="ask_place_threshold",
                                                 prompt="How far away from the mid price do you want to place the next ask"
                                                      "(Enter 0.01 to indicate 1%)? >>> ",
                                                 type_str="float",
                                                 default=0.01),
    "cancel_order_wait_time":           ConfigVar(key="cancel_order_wait_time",
                                                  prompt="How often do you want to cancel and replace bids and asks "
                                                         "(in seconds)? >>> ",
                                                  type_str="float",
                                                  default=60)
}