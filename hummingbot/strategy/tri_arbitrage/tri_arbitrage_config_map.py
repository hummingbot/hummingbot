from hummingbot.client.config.config_var import ConfigVar
import hummingbot.client.settings as settings
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_market_trading_pair,
    validate_decimal,
    validate_bool
)
from hummingbot.client.config.config_helpers import parse_cvar_value
from hummingbot.client.settings import AllConnectorSettings, required_exchanges
from decimal import Decimal
from typing import Optional


def validate_primary_market_trading_pair(value: str) -> Optional[str]:
    primary_market = tri_arbitrage_config_map.get("primary_market").value
    return validate_market_trading_pair(primary_market, value)


def validate_secondary_market_trading_pair(value: str) -> Optional[str]:
    secondary_market = tri_arbitrage_config_map.get("secondary_market").value
    return validate_market_trading_pair(secondary_market, value)

def validate_tertiary_market_trading_pair(value: str) -> Optional[str]:
    tertiary_market = tri_arbitrage_config_map.get("tertiary_market").value
    return validate_market_trading_pair(tertiary_market, value)

def primary_trading_pair_prompt():
    primary_market = tri_arbitrage_config_map.get("primary_market").value
    return "Enter the token trading pair you would like to trade on %s%s (important! should be BaseToken1/QuoteToken1)>>> " \
           % (primary_market, "e.g FRONT/BTC")

def secondary_trading_pair_prompt():
    secondary_market = tri_arbitrage_config_map.get("secondary_market").value
    return "Enter the token trading pair you would like to trade on %s%s (important! should be QuoteToken1/QuoteToken3)>>> " \
           % (secondary_market, " (e.g. BTC/USDT)")

def tertiary_trading_pair_prompt():
    tertiary_market = tri_arbitrage_config_map.get("tertiary_market").value
    return "Enter the token trading pair you would like to trade on %s%s (important! should be BaseToken1/QuoteToken3)>>> " \
           % (tertiary_market, " (e.g. FRONT/USDT)")
           
def secondary_market_on_validated(value: str):
    required_exchanges.append(value)


def update_oracle_settings(value: str):
    c_map = tri_arbitrage_config_map
    if not (c_map["use_oracle_conversion_rate"].value is not None and
            c_map["primary_market_trading_pair"].value is not None and
            c_map["secondary_market_trading_pair"].value is not None):
        return
    use_oracle = parse_cvar_value(c_map["use_oracle_conversion_rate"], c_map["use_oracle_conversion_rate"].value)
    first_base, first_quote = c_map["primary_market_trading_pair"].value.split("-")
    second_base, second_quote = c_map["secondary_market_trading_pair"].value.split("-")
    if use_oracle and (first_base != second_base or first_quote != second_quote):
        settings.required_rate_oracle = True
        settings.rate_oracle_pairs = []
        if first_base != second_base:
            settings.rate_oracle_pairs.append(f"{second_base}-{first_base}")
        if first_quote != second_quote:
            settings.rate_oracle_pairs.append(f"{second_quote}-{first_quote}")
    else:
        settings.required_rate_oracle = False
        settings.rate_oracle_pairs = []


tri_arbitrage_config_map = {
    "strategy": ConfigVar(
        key="strategy",
        prompt="",
        default="tri_arbitrage"
    ),
    "primary_market": ConfigVar(
        key="primary_market",
        prompt="Enter your primary spot connector >>> ",
        prompt_on_new=True,
        validator=validate_exchange,
        on_validated=lambda value: settings.required_exchanges.append(value),
    ),
    "secondary_market": ConfigVar(
        key="secondary_market",
        prompt="Enter your secondary spot connector >>> ",
        prompt_on_new=True,
        validator=validate_exchange,
        on_validated=lambda value: settings.required_exchanges.append(value),
    ),
    "tertiary_market": ConfigVar(
        key="tertiary_market",
        prompt="Enter your tertiary spot connector >>> ",
        prompt_on_new=True,
        validator=validate_exchange,
        on_validated=lambda value: settings.required_exchanges.append(value),
    ),
    "primary_market_trading_pair": ConfigVar(
        key="primary_market_trading_pair",
        prompt=primary_trading_pair_prompt,
        prompt_on_new=True,
        validator=validate_primary_market_trading_pair,
        on_validated=update_oracle_settings,
    ),
    "secondary_market_trading_pair": ConfigVar(
        key="secondary_market_trading_pair",
        prompt=secondary_trading_pair_prompt,
        prompt_on_new=True,
        validator=validate_secondary_market_trading_pair,
        on_validated=update_oracle_settings,
    ),
    "tertiary_market_trading_pair": ConfigVar(
        key="tertiary_market_trading_pair",
        prompt=tertiary_trading_pair_prompt,
        prompt_on_new=True,
        validator=validate_tertiary_market_trading_pair,
        on_validated=update_oracle_settings,
    ),
    "min_profitability": ConfigVar(
        key="min_profitability",
        prompt="What is the minimum profitability for you to make a trade? (Enter 1 to indicate 1%) >>> ",
        prompt_on_new=True,
        default=Decimal("0.3"),
        validator=lambda v: validate_decimal(v, Decimal(-100), Decimal("100"), inclusive=True),
        type_str="decimal",
    ),
    "maxorder_amount": ConfigVar(
        key="maxorder_amount",
        prompt="What is the order amount in USD for the trades >>> ",
        prompt_on_new=True,
        default=Decimal("1000"),
        validator=lambda v: validate_decimal(v, Decimal(0), inclusive=True),
        type_str="decimal",
    ),
    "fee_amount": ConfigVar(
        key="fee_amount",
        prompt="What is the percentage fee on trades >>> ",
        prompt_on_new=True,
        default=Decimal("0.1"),
        validator=lambda v: validate_decimal(v, Decimal(0), inclusive=True),
        type_str="decimal",
    ),
    "use_oracle_conversion_rate": ConfigVar(
        key="use_oracle_conversion_rate",
        type_str="bool",
        prompt="Strategy requires the use of rate oracle please accept (Yes/No) >>> ",
        prompt_on_new=True,
        validator=lambda v: validate_bool(v),
        on_validated=update_oracle_settings,
    ),
    "secondary_to_primary_base_conversion_rate": ConfigVar(
        key="secondary_to_primary_base_conversion_rate",
        prompt="Enter conversion rate for secondary base asset value to primary base asset value, e.g. "
               "if primary base asset is USD and the secondary is DAI, 1 DAI is valued at 1.25 USD, "
               "the conversion rate is 1.25 >>> ",
        default=Decimal("1"),
        validator=lambda v: validate_decimal(v, Decimal(0), inclusive=False),
        type_str="decimal",
    ),
    "secondary_to_primary_quote_conversion_rate": ConfigVar(
        key="secondary_to_primary_quote_conversion_rate",
        prompt="Enter conversion rate for secondary quote asset value to primary quote asset value, e.g. "
               "if primary quote asset is USD and the secondary is DAI and 1 DAI is valued at 1.25 USD, "
               "the conversion rate is 1.25 >>> ",
        default=Decimal("1"),
        validator=lambda v: validate_decimal(v, Decimal(0), inclusive=False),
        type_str="decimal",
    ),
}
