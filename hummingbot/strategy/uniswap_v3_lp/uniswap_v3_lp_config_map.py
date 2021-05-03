from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_market_trading_pair,
    validate_decimal,
)
from hummingbot.client.settings import (
    required_exchanges,
    requried_connector_trading_pairs,
    EXAMPLE_PAIRS,
)
from decimal import Decimal


def market_validator(value: str) -> None:
    exchange = "uniswap_v3"
    return validate_market_trading_pair(exchange, value)


def market_on_validated(value: str) -> None:
    required_exchanges.append(value)
    requried_connector_trading_pairs["uniswap_v3"] = [value]


def market_prompt() -> str:
    connector = "uniswap_v3"
    example = EXAMPLE_PAIRS.get(connector)
    return "Enter the pair (pool) you would like to provide liquidity to {}>>> ".format(
        f" (e.g. {example}) " if example else "")


def token_amount_prompt() -> str:
    return f"How much liquidity you want to provide on {uniswap_v3_lp_config_map['token'].value}? >>> "


uniswap_v3_lp_config_map = {
    "strategy": ConfigVar(
        key="strategy",
        prompt="",
        default="uniswap_v3_lp"),
    "market": ConfigVar(
        key="market",
        prompt=market_prompt,
        prompt_on_new=True,
        validator=market_validator,
        on_validated=market_on_validated),
    "upper_price_bound": ConfigVar(
        key="upper_price_bound",
        prompt="What is the upper price limit of the liquidity position? >>> ",
        type_str="str",
        validator=lambda v: validate_decimal(v, Decimal("0")),
        prompt_on_new=True),
    "lower_price_bound": ConfigVar(
        key="lower_price_bound",
        prompt="What is the lower price limit of the liquidity position? >>> ",
        type_str="str",
        validator=lambda v: validate_decimal(v, Decimal("0")),
        prompt_on_new=True),
    "boundaries_margin": ConfigVar(
        key="boundaries_margin",
        prompt="How much percent from the upper/lower price bound the price must move before moving the liquidity "
               "position? (Enter 1 to indicate 1%) >>> ",
        prompt_on_new=True,
        validator=lambda v: validate_decimal(v, Decimal("0")),
        type_str="decimal"),
    "token": ConfigVar(
        key="token",
        prompt="What token do you want to use to calculate the liquidity? >>> ",
        prompt_on_new=True,
        type_str="str"),
    "token_amount": ConfigVar(
        key="token_amount",
        prompt=token_amount_prompt,
        prompt_on_new=True,
        validator=lambda v: validate_decimal(v, Decimal("0")),
        type_str="decimal"),
}
