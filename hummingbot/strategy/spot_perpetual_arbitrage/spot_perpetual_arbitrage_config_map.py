from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_market_trading_pair,
    validate_connector,
    validate_derivative,
    validate_decimal,
    validate_int
)
from hummingbot.client.settings import (
    required_exchanges,
    requried_connector_trading_pairs,
    AllConnectorSettings,
)
from decimal import Decimal


def exchange_on_validated(value: str) -> None:
    required_exchanges.append(value)


def spot_market_validator(value: str) -> None:
    exchange = spot_perpetual_arbitrage_config_map["spot_connector"].value
    return validate_market_trading_pair(exchange, value)


def spot_market_on_validated(value: str) -> None:
    requried_connector_trading_pairs[spot_perpetual_arbitrage_config_map["spot_connector"].value] = [value]


def perpetual_market_validator(value: str) -> None:
    exchange = spot_perpetual_arbitrage_config_map["perpetual_connector"].value
    return validate_market_trading_pair(exchange, value)


def perpetual_market_on_validated(value: str) -> None:
    requried_connector_trading_pairs[spot_perpetual_arbitrage_config_map["perpetual_connector"].value] = [value]


def spot_market_prompt() -> str:
    connector = spot_perpetual_arbitrage_config_map.get("spot_connector").value
    example = AllConnectorSettings.get_example_pairs().get(connector)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (connector, f" (e.g. {example})" if example else "")


def perpetual_market_prompt() -> str:
    connector = spot_perpetual_arbitrage_config_map.get("perpetual_connector").value
    example = AllConnectorSettings.get_example_pairs().get(connector)
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
    "perpetual_connector": ConfigVar(
        key="perpetual_connector",
        prompt="Enter a derivative name (Exchange/AMM) >>> ",
        prompt_on_new=True,
        validator=validate_derivative,
        on_validated=exchange_on_validated),
    "perpetual_market": ConfigVar(
        key="perpetual_market",
        prompt=perpetual_market_prompt,
        prompt_on_new=True,
        validator=perpetual_market_validator,
        on_validated=perpetual_market_on_validated),
    "order_amount": ConfigVar(
        key="order_amount",
        prompt=order_amount_prompt,
        type_str="decimal",
        prompt_on_new=True),
    "perpetual_leverage": ConfigVar(
        key="perpetual_leverage",
        prompt="How much leverage would you like to use on the perpetual exchange? (Enter 1 to indicate 1X) >>> ",
        type_str="int",
        default=1,
        validator= lambda v: validate_int(v),
        prompt_on_new=True),
    "min_opening_arbitrage_pct": ConfigVar(
        key="min_opening_arbitrage_pct",
        prompt="What is the minimum arbitrage percentage between the spot and perpetual market price before opening "
               "an arbitrage position? (Enter 1 to indicate 1%) >>> ",
        prompt_on_new=True,
        default=Decimal("1"),
        validator=lambda v: validate_decimal(v, Decimal(-100), 100, inclusive=False),
        type_str="decimal"),
    "min_closing_arbitrage_pct": ConfigVar(
        key="min_closing_arbitrage_pct",
        prompt="What is the minimum arbitrage percentage between the spot and perpetual market price before closing "
               "an existing arbitrage position? (Enter 1 to indicate 1%) (This can be negative value to close out the "
               "position with lesser profit at higher chance of closing) >>> ",
        prompt_on_new=True,
        default=Decimal("-0.1"),
        validator=lambda v: validate_decimal(v, Decimal(-100), 100, inclusive=False),
        type_str="decimal"),
    "spot_market_slippage_buffer": ConfigVar(
        key="spot_market_slippage_buffer",
        prompt="How much buffer do you want to add to the price to account for slippage for orders on the spot market "
               "(Enter 1 for 1%)? >>> ",
        prompt_on_new=True,
        default=Decimal("0.05"),
        validator=lambda v: validate_decimal(v),
        type_str="decimal"),
    "perpetual_market_slippage_buffer": ConfigVar(
        key="perpetual_market_slippage_buffer",
        prompt="How much buffer do you want to add to the price to account for slippage for orders on the perpetual "
               "market (Enter 1 for 1%)? >>> ",
        prompt_on_new=True,
        default=Decimal("0.05"),
        validator=lambda v: validate_decimal(v),
        type_str="decimal"),
    "next_arbitrage_opening_delay": ConfigVar(
        key="next_arbitrage_opening_delay",
        prompt="How long do you want the strategy to wait before opening the next arbitrage position (in seconds)?",
        type_str="float",
        validator=lambda v: validate_decimal(v, min_value=0, inclusive=False),
        default=120),
}
