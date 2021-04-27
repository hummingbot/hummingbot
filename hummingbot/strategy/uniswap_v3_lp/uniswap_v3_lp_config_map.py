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
    return "Enter the trading pair (pool) you would like to provide liquidity to {}>>> ".format(
        f" (e.g. {example}) " if example else "")


def range_order_quote_amount_prompt() -> str:
    trading_pair = uniswap_v3_lp_config_map["market"].value
    base_asset, quote_asset = trading_pair.split("-")
    return f"What is the amount of {quote_asset} you want to use for your range order? >>> "


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
    "range_order_quote_amount": ConfigVar(
        key="range_order_quote_amount",
        prompt=range_order_quote_amount_prompt,
        type_str="decimal",
        validator=lambda v: validate_decimal(v, Decimal("0")),
        prompt_on_new=True),
    "range_order_spread": ConfigVar(
        key="range_order_spread",
        prompt="What is the spread for your range order? (Enter 1 to indicate 1%) >>> ",
        prompt_on_new=True,
        validator=lambda v: validate_decimal(v, Decimal("0")),
        type_str="decimal"),
}
