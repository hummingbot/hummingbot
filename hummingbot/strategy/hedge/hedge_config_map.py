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


def token_validate(value: str) -> Optional[str]:
    value = value.upper()
    markets = list(hedge_config_map["maker_markets"].value.split(","))
    tokens = set()
    for market in markets:
        # Tokens in markets already validated in market_validate()
        for token in market.strip().upper().split("-"):
            tokens.add(token.strip())
    if value not in tokens:
        return f"Invalid token. {value} is not one of {','.join(sorted(tokens))}"


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
    "maker_markets":
        ConfigVar(key="maker_markets",
                  prompt="Enter a list of markets to execute on taker market for each asset(comma separated, e.g. LTC-USDT,ETH-USDT) >>> ",
                  type_str="str",
                  validator=market_validate,
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
    "hedge_asset":
        ConfigVar(key="hedge_asset",
                  prompt="What asset (base or quote) is used as the hedge? >>> ",
                  type_str="str",
                  validator=token_validate,
                  prompt_on_new=True),
    "hedge_interval":
        ConfigVar(key="hedge_interval",
                  prompt="how often do you want to check the hedge >>> ",
                  type_str="decimal",
                  default=Decimal(0.1),
                  validator=lambda v: validate_decimal(v, min_value=0, inclusive=False),
                  prompt_on_new=True),
    "hedge_ratio":
        ConfigVar(key="hedge_ratio",
                  prompt="Enter ratio of base asset to hedge >>> ",
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
    "minimum_trade":
        ConfigVar(key="minimum_trade",
                  prompt="Enter minimum trade size in hedge asset >>> ",
                  default=Decimal("10"),
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, inclusive=False),
                  prompt_on_new=True),

}
