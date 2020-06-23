from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_market_trading_pair,
    validate_decimal
)
from hummingbot.client.settings import (
    required_exchanges,
    EXAMPLE_PAIRS,
)
from hummingbot.data_feed.exchange_price_manager import ExchangePriceManager
from decimal import Decimal
from typing import Optional


def validate_primary_market_trading_pair(value: str) -> Optional[str]:
    primary_market = arbitrage_config_map.get("primary_market").value
    return validate_market_trading_pair(primary_market, value)


def validate_secondary_market_trading_pair(value: str) -> Optional[str]:
    secondary_market = arbitrage_config_map.get("secondary_market").value
    return validate_market_trading_pair(secondary_market, value)


def primary_trading_pair_prompt():
    primary_market = arbitrage_config_map.get("primary_market").value
    example = EXAMPLE_PAIRS.get(primary_market)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (primary_market, f" (e.g. {example})" if example else "")


def secondary_trading_pair_prompt():
    secondary_market = arbitrage_config_map.get("secondary_market").value
    example = EXAMPLE_PAIRS.get(secondary_market)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (secondary_market, f" (e.g. {example})" if example else "")


def secondary_market_on_validated(value: str):
    required_exchanges.append(value)
    primary_exchange = arbitrage_config_map["primary_market"].value
    ExchangePriceManager.set_exchanges_to_feed([primary_exchange, value])
    ExchangePriceManager.start()


arbitrage_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="arbitrage"),
    "primary_market": ConfigVar(
        key="primary_market",
        prompt="Enter your primary exchange name >>> ",
        prompt_on_new=True,
        validator=validate_exchange,
        on_validated=lambda value: required_exchanges.append(value)),
    "secondary_market": ConfigVar(
        key="secondary_market",
        prompt="Enter your secondary exchange name >>> ",
        prompt_on_new=True,
        validator=validate_exchange,
        on_validated=secondary_market_on_validated),
    "primary_market_trading_pair": ConfigVar(
        key="primary_market_trading_pair",
        prompt=primary_trading_pair_prompt,
        prompt_on_new=True,
        validator=validate_primary_market_trading_pair),
    "secondary_market_trading_pair": ConfigVar(
        key="secondary_market_trading_pair",
        prompt=secondary_trading_pair_prompt,
        prompt_on_new=True,
        validator=validate_secondary_market_trading_pair),
    "min_profitability": ConfigVar(
        key="min_profitability",
        prompt="What is the minimum profitability for you to make a trade? (Enter 1 to indicate 1%) >>> ",
        prompt_on_new=True,
        default=0.3,
        validator=lambda v: validate_decimal(v, Decimal(0), Decimal("100"), inclusive=False),
        type_str="decimal"),
}
