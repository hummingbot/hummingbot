import re
from decimal import Decimal
from typing import Optional

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_derivative,
    validate_exchange,
    validate_decimal,
    validate_int,
)


def market_validate(value: str) -> Optional[str]:
    pairs = list()
    if len(value.strip()) == 0:
        # Whitespace
        return "Invalid market(s). The given entry is empty."
    markets = list(value.upper().split(","))
    for market in markets:
        if len(market.strip()) == 0:
            return "Invalid markets. The given entry contains an empty market."
        tokens = market.strip().split("-")
        if len(tokens) != 2:
            return f"Invalid market. {market} doesn't contain exactly 2 tickers."
        for token in tokens:
            # Check allowed ticker lengths
            if len(token.strip()) == 0:
                return f"Invalid market. Ticker {token} has an invalid length."
            if(bool(re.search('^[a-zA-Z0-9]*$', token)) is False):
                return f"Invalid market. Ticker {token} contains invalid characters."
        # The pair is valid
        pair = f"{tokens[0]}-{tokens[1]}"
        if pair in pairs:
            return f"Duplicate market {pair}."
        pairs.append(pair)


def asset_validate(value: str) -> Optional[str]:
    tokens_list = list()
    if len(value.strip()) == 0:
        # Whitespace
        return "Invalid market(s). The given entry is empty."
    markets = list(value.upper().split(","))
    for market in markets:
        if len(market.strip()) == 0:
            return "Invalid assets. The given entry contains an empty market."
        tokens = market.strip().split("-")
        if len(tokens) >= 2:
            return f"Invalid asset. {market} contain more than 1 asset."
        for token in tokens:
            # Check allowed ticker lengths
            if len(token.strip()) == 0:
                return f"Invalid market. Ticker {token} has an invalid length."
            if(bool(re.search('^[a-zA-Z0-9]*$', token)) is False):
                return f"Invalid market. Ticker {token} contains invalid characters."
            # The pair is valid

            if token in tokens_list:
                return f"Duplicate market {token}."
            tokens_list.append(token)


# List of parameters defined by the strategy
hedge_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="hedge"),
    "maker_exchange":
        ConfigVar(key="maker_exchange",
                  prompt="Enter the spot connector to use for target market >>> ",
                  validator=validate_exchange,
                  prompt_on_new=True),
    "maker_assets":
        ConfigVar(key="maker_assets",
                  prompt="Enter a list of assets to hedge on taker market(comma separated, e.g. LTC,ETH) >>> ",
                  type_str="str",
                  validator=asset_validate,
                  prompt_on_new=True),
    "taker_exchange":
        ConfigVar(key="taker_exchange",
                  prompt="Enter the derivative connector to use for taker market >>> ",
                  validator=validate_derivative,
                  prompt_on_new=True),
    "taker_markets":
        ConfigVar(key="taker_markets",
                  prompt="Enter a list of markets to execute on taker market for each asset(comma separated, e.g. LTC-USDT,ETH-USDT) >>> ",
                  type_str="str",
                  validator=market_validate,
                  prompt_on_new=True),
    "hedge_interval":
        ConfigVar(key="hedge_interval",
                  prompt="how often do you want to check the hedge >>> ",
                  type_str="decimal",
                  default=Decimal(10),
                  validator=lambda v: validate_decimal(v, min_value=0, inclusive=False),
                  prompt_on_new=True),
    "hedge_ratio":
        ConfigVar(key="hedge_ratio",
                  prompt="Enter ratio of base asset to hedge, e.g 0.5 -> 0.5 BTC will be short for every 1 BTC bought on maker market >>> ",
                  default=Decimal("1"),
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, inclusive=False),
                  prompt_on_new=True),
    "leverage":
        ConfigVar(key="leverage",
                  prompt="How much leverage do you want to use? >>> ",
                  type_str="int",
                  default=int(10),
                  validator=lambda v: validate_int(v, min_value=0, inclusive=False),
                  prompt_on_new=True),
    "max_order_age":
        ConfigVar(key="max_order_age",
                  prompt="Max Order Age in seconds? >>> ",
                  type_str="float",
                  default=float(100),
                  validator=lambda v: validate_decimal(v),
                  prompt_on_new=True),
    "slippage":
        ConfigVar(key="slippage",
                  prompt="Enter max slippage in decimal, e.g 0.1 -> 10% >>> ",
                  default=Decimal("0.01"),
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v),
                  prompt_on_new=True),
    "minimum_trade":
        ConfigVar(key="minimum_trade",
                  prompt="Enter minimum trade size in hedge asset >>> ",
                  default=Decimal("10"),
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, inclusive=False),
                  prompt_on_new=True),
}
