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
    market = dev_4_twap_config_map.get("market").value
    example = EXAMPLE_PAIRS.get(market)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (market, f" (e.g. {example})" if example else "")


def str2bool(value: str):
    return str(value).lower() in ("yes", "true", "t", "1")


# checks if the trading pair is valid
def validate_market_trading_pair_tuple(value: str) -> Optional[str]:
    market = dev_4_twap_config_map.get("market").value
    return validate_market_trading_pair(market, value)


dev_4_twap_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="dev_4_twap"),
    "market":
        ConfigVar(key="market",
                  prompt="Enter the name of the exchange >>> ",
                  validator=validate_exchange,
                  on_validated=lambda value: required_exchanges.append(value)),
    "market_trading_pair_tuple":
        ConfigVar(key="market_trading_pair_tuple",
                  prompt=trading_pair_prompt,
                  validator=validate_market_trading_pair_tuple),
    "order_type":
        ConfigVar(key="order_type",
                  prompt="Enter type of order (limit/market) default is market >>> ",
                  type_str="str",
                  validator=lambda v: None if v in {"limit", "market", ""} else "Invalid order type.",
                  default="market"),
    "order_amount":
        ConfigVar(key="order_amount",
                  prompt="What is your preferred quantity (denominated in the base asset, default is 1)? "
                         ">>> ",
                  default=1.0,
                  type_str="float"),
    "is_buy":
        ConfigVar(key="is_buy",
                  prompt="Enter True for Buy order and False for Sell order (default is Buy Order) >>> ",
                  type_str="bool",
                  default=True),
    "num_individual_orders":
        ConfigVar(key="num_individual_orders",
                  prompt="Into how many individual orders do you want to split this order? (Enter 10 to indicate 10 individual orders. "
                         "Default is 1)? >>> ",
                  type_str="float",
                  default=1),
    "time_delay":
        ConfigVar(key="time_delay",
                  prompt="How many seconds do you want to wait between each individual order? (Enter 10 to indicate 10 seconds. "
                         "Default is 10)? >>> ",
                  type_str="float",
                  default=10),
    "order_price":
        ConfigVar(key="order_price",
                  prompt="What is the price of the limit order ? >>> ",
                  required_if=lambda: dev_4_twap_config_map.get("order_type").value == "limit",
                  type_str="float"),
    "cancel_order_wait_time":
        ConfigVar(key="cancel_order_wait_time",
                  prompt="How long do you want to wait before cancelling your limit order (in seconds). "
                         "(Default is 60 seconds) ? >>> ",
                  required_if=lambda: dev_4_twap_config_map.get("order_type").value == "limit",
                  type_str="float",
                  default=60),

}
