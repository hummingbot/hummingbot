from decimal import Decimal
from typing import Optional

from hummingbot.client.config.config_validators import (
    validate_bool,
    validate_connector,
    validate_decimal,
    validate_int,
    validate_market_trading_pair,
)
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import required_exchanges

MAX_CONNECTOR = 5


def validate_exchange_trading_pair(value: str) -> Optional[str]:
    exchange = hedge_v2_config_map.get("hedge_connector").value
    return validate_market_trading_pair(exchange, value)


def market_validate(exchange: str, value: str) -> Optional[str]:
    markets = value.split(",")
    for market in markets:
        validated = validate_market_trading_pair(exchange, market)
        if validated:
            return validated
    return None


hedge_v2_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="hedge_v2"),
    "hedge_connector":
        ConfigVar(key="hedge_connector",
                  prompt="Enter the connector to use to hedge overall asset >>> ",
                  validator=validate_connector,
                  on_validated=lambda value: required_exchanges.add(value),
                  prompt_on_new=True),
    "hedge_market":
        ConfigVar(key="hedge_market",
                  prompt="Enter the market to hedge the asset value. >>> ",
                  type_str="str",
                  validator=validate_exchange_trading_pair,
                  prompt_on_new=True),
    "hedge_leverage":
        ConfigVar(key="hedge_leverage",
                  prompt="How much leverage do you want to use? applicable for derivatives only >>> ",
                  type_str="int",
                  default=int(1),
                  validator=lambda v: validate_int(v, min_value=1, inclusive=True),
                  prompt_on_new=False),
    "hedge_interval":
        ConfigVar(key="hedge_interval",
                  prompt="how often do you want to check the hedge >>> ",
                  type_str="decimal",
                  default=Decimal(10),
                  validator=lambda v: validate_decimal(v, min_value=0, inclusive=False),
                  prompt_on_new=False),
    "hedge_ratio":
        ConfigVar(key="hedge_ratio",
                  prompt="Enter ratio of asset to hedge, e.g 0.5 means 50 percent of the total asset value will be hedged. >>> ",
                  default=Decimal("1"),
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v),
                  prompt_on_new=False),
    "min_trade_size":
        ConfigVar(key="min_trade_size",
                  prompt="Enter minimum trade size in quote asset >>> ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, inclusive=True),
                  prompt_on_new=True),
    "max_order_age":
        ConfigVar(key="max_order_age",
                  prompt="Max Order Age in seconds? >>> ",
                  type_str="float",
                  default=float(100),
                  validator=lambda v: validate_decimal(v, 0, inclusive=True),
                  prompt_on_new=False),
    "slippage":
        ConfigVar(key="slippage",
                  prompt="Enter max slippage in decimal, e.g 0.1 -> 10% >>> ",
                  default=Decimal("0.01"),
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, inclusive=True),
                  prompt_on_new=False),
}

for i in range(MAX_CONNECTOR):
    hedge_v2_config_map[f"enable_connector_{i}"] = ConfigVar(
        key=f"enable_connector_{i}",
        prompt=f"Enable connector {i} (y/n) >>> ",
        type_str="bool",
        validator=validate_bool,
        prompt_on_new=True)
    hedge_v2_config_map[f"connector_{i}"] = ConfigVar(
        key=f"connector_{i}",
        prompt="Enter the connector to be hedged >>> ",
        validator=validate_connector,
        on_validated=lambda value: required_exchanges.add(value),
        required_if=lambda i=i: hedge_v2_config_map.get(f"enable_connector_{i}").value is True,
        prompt_on_new=True)
    hedge_v2_config_map[f"markets_{i}"] = ConfigVar(
        key=f"markets_{i}",
        prompt=
        "Enter the markets to check amount to hedge comma seperated. "
        "Use the market with the quote asset same as the hedge market. "
        "This will be used to calculate the total value in the quote asset to be hedged. "
        "e.g if hedge_market is BTC-USDT, the taker market can be BTC-USDT,ETH-USDT>>> ",
        type_str="str",
        validator=lambda x: market_validate(hedge_v2_config_map[f"connector_{i}"], x),
        required_if=lambda i=i: hedge_v2_config_map.get(f"enable_connector_{i}").value is True,
        prompt_on_new=True)
