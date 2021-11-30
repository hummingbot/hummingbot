from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_decimal,
)
import hummingbot.client.settings as settings
from decimal import Decimal


def target_currency_prompt():
    exchange = triangular_arbitrage_config_map.get("exchange").value
    return "Enter the name of the currency you would like to accrue on " \
           f"{exchange} >>> "


def first_auxilliary_prompt():
    exchange = triangular_arbitrage_config_map.get("exchange").value
    return "Enter the name of the first auxilliary currency to use on " \
           f"{exchange} >>> "


def second_auxilliary_prompt():
    exchange = triangular_arbitrage_config_map.get("exchange").value
    return "Enter the name of the second auxilliary currency to use on " \
           f"{exchange} >>> "


def primary_market_prompt():
    target_node = triangular_arbitrage_config_map.get("target_node").value
    left_node = triangular_arbitrage_config_map.get("left_node").value
    return "Enter the exchange on which you would like the trading pair which connects " \
        f"{target_node} to {left_node} to reside >>> "


def tertiary_market_prompt():
    target_node = triangular_arbitrage_config_map.get("target_node").value
    right_node = triangular_arbitrage_config_map.get("right_node").value
    return "Enter the exchange on which you would like the trading pair which connects " \
        f"{target_node} to {right_node} to reside >>> "


def secondary_market_prompt():
    left_node = triangular_arbitrage_config_map.get("left_node").value
    right_node = triangular_arbitrage_config_map.get("right_node").value
    return "Enter the exchange on which you would like the trading pair which connects " \
        f"{left_node} to {right_node} to reside >>> "


def primary_source_prompt():
    primary_market = triangular_arbitrage_config_map.get("primary_market").value
    target_node = triangular_arbitrage_config_map.get("target_node").value
    return f"Enter the asset symbol on {primary_market} which represents " \
           f"{target_node} >>> "


def tertiary_source_prompt():
    tertiary_market = triangular_arbitrage_config_map.get("tertiary_market").value
    right_node = triangular_arbitrage_config_map.get("right_node").value
    return f"Enter the asset symbol on {tertiary_market} which represents " \
           f"{right_node} >>> "


def secondary_source_prompt():
    secondary_market = triangular_arbitrage_config_map.get("secondary_market").value
    left_node = triangular_arbitrage_config_map.get("left_node").value
    return f"Enter the asset symbol on {secondary_market} which represents " \
           f"{left_node} >>> "


def primary_target_prompt():
    primary_market = triangular_arbitrage_config_map.get("primary_market").value
    left_node = triangular_arbitrage_config_map.get("left_node").value
    return f"Enter the asset symbol on {primary_market} which represents " \
           f"{left_node} >>> "


def secondary_target_prompt():
    secondary_market = triangular_arbitrage_config_map.get("secondary_market").value
    right_node = triangular_arbitrage_config_map.get("right_node").value
    return f"Enter the asset symbol on {secondary_market} which represents " \
           f"{right_node} >>> "


def tertiary_target_prompt():
    tertiary_market = triangular_arbitrage_config_map.get("tertiary_market").value
    target_node = triangular_arbitrage_config_map.get("target_node").value
    return f"Enter the asset symbol on {tertiary_market} which represents " \
           f"{target_node} >>> "


def secondary_market_on_validated(value: str):
    settings.required_exchanges.append(value)


def tertiary_market_on_validated(value: str):
    settings.required_exchanges.append(value)


def replacement_source_left_prompt():
    source = triangular_arbitrage_config_map.get("target_currency").value
    target = triangular_arbitrage_config_map.get("first_aux_currency").value
    return f"Enter the name of the currency which will be used for {source} " \
           f"on the edge which connects {source} to {target} >>> "


def replacement_target_left_prompt():
    source = triangular_arbitrage_config_map.get("target_currency").value
    target = triangular_arbitrage_config_map.get("first_aux_currency").value
    return f"Enter the name of the currency which will be used for {target} " \
           f"on the edge which connects {source} to {target} >>> "


def replacement_source_bottom_prompt():
    source = triangular_arbitrage_config_map.get("first_aux_currency").value
    target = triangular_arbitrage_config_map.get("second_aux_currency").value
    return f"Enter the name of the currency which will be used for {source} " \
           f"on the edge which connects {source} to {target} >>> "


def replacement_target_bottom_prompt():
    source = triangular_arbitrage_config_map.get("first_aux_currency").value
    target = triangular_arbitrage_config_map.get("second_aux_currency").value
    return f"Enter the name of the currency which will be used for {target} " \
           f"on the edge which connects {source} to {target} >>> "


def replacement_source_right_prompt():
    source = triangular_arbitrage_config_map.get("second_aux_currency").value
    target = triangular_arbitrage_config_map.get("target_currency").value
    return f"Enter the name of the currency which will be used for {source} " \
           f"on the edge which connects {source} to {target} >>> "


def replacement_target_right_prompt():
    source = triangular_arbitrage_config_map.get("second_aux_currency").value
    target = triangular_arbitrage_config_map.get("target_currency").value
    return f"Enter the name of the currency which will be used for {target} " \
           f"on the edge which connects {source} to {target} >>> "


triangular_arbitrage_config_map = {
    "strategy": ConfigVar(
        key="strategy",
        prompt="",
        default="triangular_arbitrage"
    ),
    "exchange": ConfigVar(
        key="exchange",
        required_if=lambda: True,
        validator=validate_exchange,
        on_validated=lambda value: settings.required_exchanges.append(value),
        prompt="Enter the name of the exchange on which you would like to trade >>> ",
        prompt_on_new=True
    ),
    "target_currency": ConfigVar(
        key="target_currency",
        prompt=target_currency_prompt,
        prompt_on_new=True,
        required_if=lambda: True
    ),
    "first_aux_currency": ConfigVar(
        key="first_aux_currency",
        prompt=first_auxilliary_prompt,
        prompt_on_new=True,
        required_if=lambda: True
    ),
    "second_aux_currency": ConfigVar(
        key="second_aux_currency",
        prompt=second_auxilliary_prompt,
        prompt_on_new=True,
        required_if=lambda: True
    ),
    "min_profitability": ConfigVar(
        key="min_profitability",
        prompt="What is the minimum profitability for you to make a trade? (Enter 1 to indicate 1%) >>> ",
        prompt_on_new=True,
        default=Decimal("0.3"),
        validator=lambda v: validate_decimal(v, Decimal(-100), Decimal("100"), inclusive=True),
        type_str="decimal",
    ),
    "replacement_source_currency_on_left_edge": ConfigVar(
        key="replacement_source_currency_on_left_edge",
        prompt=replacement_source_left_prompt,
        prompt_on_new=False,
        default=None,
        required_if=lambda: False
    ),
    "replacement_target_currency_on_left_edge": ConfigVar(
        key="replacement_target_currency_on_left_edge",
        prompt=replacement_target_left_prompt,
        prompt_on_new=False,
        default=None,
        required_if=lambda: False
    ),
    "replacement_source_currency_on_bottom_edge": ConfigVar(
        key="replacement_source_currency_on_bottom_edge",
        prompt=replacement_source_bottom_prompt,
        prompt_on_new=False,
        default=None,
        required_if=lambda: False
    ),
    "replacement_target_currency_on_bottom_edge": ConfigVar(
        key="replacement_target_currency_on_bottom_edge",
        prompt=replacement_target_bottom_prompt,
        prompt_on_new=False,
        default=None,
        required_if=lambda: False
    ),
    "replacement_source_currency_on_right_edge": ConfigVar(
        key="replacement_source_currency_on_right_edge",
        prompt=replacement_source_right_prompt,
        prompt_on_new=False,
        default=None,
        required_if=lambda: False
    ),
    "replacement_target_currency_on_right_edge": ConfigVar(
        key="replacement_target_currency_on_right_edge",
        prompt=replacement_target_right_prompt,
        prompt_on_new=False,
        default=None,
        required_if=lambda: False
    ),
    "fee_override": ConfigVar(
        key="fee_override",
        prompt="Enter the approximate fee percentage to use in arbitrage optimization calculations (1% = 0.01) >>> ",
        prompt_on_new=True,
        default=None,
        required_if=lambda: True,
        type_str="decimal"
    ),
}
