from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_market_trading_pair,
    validate_derivative,
    validate_decimal,
    validate_bool,
    validate_int
)
from hummingbot.client.settings import (
    required_exchanges,
    requried_connector_trading_pairs,
    EXAMPLE_PAIRS,
)
from decimal import Decimal


def exchange_on_validated(value: str) -> None:
    required_exchanges.append(value)


def primary_market_validator(value: str) -> None:
    exchange = perpetual_arbitrage_config_map["primary_connector"].value
    return validate_market_trading_pair(exchange, value)


def primary_market_on_validated(value: str) -> None:
    requried_connector_trading_pairs[perpetual_arbitrage_config_map["primary_connector"].value] = [value]


def secondary_market_validator(value: str) -> None:
    exchange = perpetual_arbitrage_config_map["secondary_connector"].value
    return validate_market_trading_pair(exchange, value)


def secondary_market_on_validated(value: str) -> None:
    requried_connector_trading_pairs[perpetual_arbitrage_config_map["secondary_connector"].value] = [value]


def primary_market_prompt() -> str:
    connector = perpetual_arbitrage_config_map.get("primary_connector").value
    example = EXAMPLE_PAIRS.get(connector)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (connector, f" (e.g. {example})" if example else "")


def secondary_market_prompt() -> str:
    connector = perpetual_arbitrage_config_map.get("secondary_connector").value
    example = EXAMPLE_PAIRS.get(connector)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (connector, f" (e.g. {example})" if example else "")


def order_amount_prompt() -> str:
    trading_pair = perpetual_arbitrage_config_map["primary_market"].value
    base_asset, quote_asset = trading_pair.split("-")
    return f"What is the amount of {base_asset} per order? >>> "


perpetual_arbitrage_config_map = {
    "strategy": ConfigVar(
        key="strategy",
        prompt="",
        default="perpetual_arbitrage"),
    "primary_connector": ConfigVar(
        key="primary_connector",
        prompt="Enter a primary connector (Exchange/AMM) >>> ",
        prompt_on_new=True,
        validator=validate_derivative,
        on_validated=exchange_on_validated),
    "primary_market": ConfigVar(
        key="primary_market",
        prompt=primary_market_prompt,
        prompt_on_new=True,
        validator=primary_market_validator,
        on_validated=primary_market_on_validated),
    "secondary_connector": ConfigVar(
        key="secondary_connector",
        prompt="Enter a secondary name (Exchange/AMM) >>> ",
        prompt_on_new=True,
        validator=validate_derivative,
        on_validated=exchange_on_validated),
    "secondary_market": ConfigVar(
        key="secondary_market",
        prompt=secondary_market_prompt,
        prompt_on_new=True,
        validator=secondary_market_validator,
        on_validated=secondary_market_on_validated),
    "order_amount": ConfigVar(
        key="order_amount",
        prompt=order_amount_prompt,
        type_str="decimal",
        prompt_on_new=True),
    "derivative_leverage": ConfigVar(
        key="derivative_leverage",
        prompt="How much leverage would you like to use on the derivative exchange? (Enter 1 to indicate 1X) ",
        type_str="int",
        default=1,
        validator= lambda v: validate_int(v),
        prompt_on_new=True),
    "min_divergence": ConfigVar(
        key="min_divergence",
        prompt="What is the minimum spread between the primary and secondary market price before starting an arbitrage? (Enter 1 to indicate 1%) >>> ",
        prompt_on_new=True,
        default=Decimal("1"),
        validator=lambda v: validate_decimal(v, 0, 100, inclusive=False),
        type_str="decimal"),
    "min_convergence": ConfigVar(
        key="min_convergence",
        prompt="What is the minimum spread between the primary and secondary market price before closing an existing arbitrage? (Enter 1 to indicate 1%) >>> ",
        prompt_on_new=True,
        default=Decimal("0.1"),
        validator=lambda v: validate_decimal(v, 0, perpetual_arbitrage_config_map["min_divergence"].value),
        type_str="decimal"),
    "maximize_funding_rate": ConfigVar(
        key="maximize_funding_rate",
        prompt="Would you like to take advantage of the funding rate on the derivative exchange, even if min convergence is reached during funding time? (True/False) >>> ",
        prompt_on_new=True,
        default=False,
        validator=validate_bool,
        type_str="bool"),
    "primary_market_slippage_buffer": ConfigVar(
        key="primary_market_slippage_buffer",
        prompt="How much buffer do you want to add to the price to account for slippage for orders on the primary market "
               "(Enter 1 for 1%)? >>> ",
        prompt_on_new=True,
        default=Decimal("0.05"),
        validator=lambda v: validate_decimal(v),
        type_str="decimal"),
    "secondary_market_slippage_buffer": ConfigVar(
        key="secondary_market_slippage_buffer",
        prompt="How much buffer do you want to add to the price to account for slippage for orders on the secondary market"
               " (Enter 1 for 1%)? >>> ",
        prompt_on_new=True,
        default=Decimal("0.05"),
        validator=lambda v: validate_decimal(v),
        type_str="decimal"),
    "next_arbitrage_cycle_delay": ConfigVar(
        key="next_arbitrage_cycle_delay",
        prompt="How long do you want the strategy to wait to cool off from an arbitrage cycle (in seconds)?",
        type_str="float",
        validator=lambda v: validate_decimal(v, min_value=0, inclusive=False),
        default=120),
}
