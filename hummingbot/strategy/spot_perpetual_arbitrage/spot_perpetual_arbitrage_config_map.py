from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_market_trading_pair,
    validate_connector,
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


def spot_market_validator(value: str) -> None:
    exchange = spot_perpetual_arbitrage_config_map["spot_connector"].value
    return validate_market_trading_pair(exchange, value)


def spot_market_on_validated(value: str) -> None:
    requried_connector_trading_pairs[spot_perpetual_arbitrage_config_map["spot_connector"].value] = [value]


def derivative_market_validator(value: str) -> None:
    exchange = spot_perpetual_arbitrage_config_map["derivative_connector"].value
    return validate_market_trading_pair(exchange, value)


def derivative_market_on_validated(value: str) -> None:
    requried_connector_trading_pairs[spot_perpetual_arbitrage_config_map["derivative_connector"].value] = [value]


def spot_market_prompt() -> str:
    connector = spot_perpetual_arbitrage_config_map.get("spot_connector").value
    example = EXAMPLE_PAIRS.get(connector)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (connector, f" (e.g. {example})" if example else "")


def derivative_market_prompt() -> str:
    connector = spot_perpetual_arbitrage_config_map.get("derivative_connector").value
    example = EXAMPLE_PAIRS.get(connector)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (connector, f" (e.g. {example})" if example else "")


def order_amount_prompt() -> str:
    trading_pair = spot_perpetual_arbitrage_config_map["spot_market"].value
    base_asset, quote_asset = trading_pair.split("-")
    return f"What is the amount of {base_asset} per order? >>> "


spot_perpetual_arbitrage_config_map = {
    "strategy": ConfigVar(
        key="strategy",
        prompt="",
        default="spot_perpetual_arbitrage"),
    "spot_connector": ConfigVar(
        key="spot_connector",
        prompt="Enter a spot connector (Exchange/AMM) >>> ",
        prompt_on_new=True,
        validator=validate_connector,
        on_validated=exchange_on_validated),
    "spot_market": ConfigVar(
        key="spot_market",
        prompt=spot_market_prompt,
        prompt_on_new=True,
        validator=spot_market_validator,
        on_validated=spot_market_on_validated),
    "derivative_connector": ConfigVar(
        key="derivative_connector",
        prompt="Enter a derivative name (Exchange/AMM) >>> ",
        prompt_on_new=True,
        validator=validate_derivative,
        on_validated=exchange_on_validated),
    "derivative_market": ConfigVar(
        key="derivative_market",
        prompt=derivative_market_prompt,
        prompt_on_new=True,
        validator=derivative_market_validator,
        on_validated=derivative_market_on_validated),
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
        prompt="What is the minimum spread between the spot and derivative market price before starting an arbitrage? (Enter 1 to indicate 1%) >>> ",
        prompt_on_new=True,
        default=Decimal("1"),
        validator=lambda v: validate_decimal(v, 0, 100, inclusive=False),
        type_str="decimal"),
    "min_convergence": ConfigVar(
        key="min_convergence",
        prompt="What is the minimum spread between the spot and derivative market price before closing an existing arbitrage? (Enter 1 to indicate 1%) >>> ",
        prompt_on_new=True,
        default=Decimal("0.1"),
        validator=lambda v: validate_decimal(v, 0, spot_perpetual_arbitrage_config_map["min_divergence"].value),
        type_str="decimal"),
    "maximize_funding_rate": ConfigVar(
        key="maximize_funding_rate",
        prompt="Would you like to take advantage of the funding rate on the derivative exchange, even if min convergence is reached during funding time? (True/False) >>> ",
        prompt_on_new=True,
        default=False,
        validator=validate_bool,
        type_str="bool"),
    "spot_market_slippage_buffer": ConfigVar(
        key="spot_market_slippage_buffer",
        prompt="How much buffer do you want to add to the price to account for slippage for orders on the spot market "
               "(Enter 1 for 1%)? >>> ",
        prompt_on_new=True,
        default=Decimal("0.05"),
        validator=lambda v: validate_decimal(v),
        type_str="decimal"),
    "derivative_market_slippage_buffer": ConfigVar(
        key="derivative_market_slippage_buffer",
        prompt="How much buffer do you want to add to the price to account for slippage for orders on the derivative market"
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
