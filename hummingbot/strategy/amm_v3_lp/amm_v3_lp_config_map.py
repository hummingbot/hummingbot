from decimal import Decimal

from hummingbot.client.config.config_validators import validate_decimal, validate_market_trading_pair
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import (
    AllConnectorSettings,
    ConnectorType,
    required_exchanges,
    requried_connector_trading_pairs,
)


def exchange_on_validated(value: str):
    required_exchanges.add(value)


def validate_connector(value: str):
    connector = AllConnectorSettings.get_connector_settings().get(value, None)
    if not connector or connector.type != ConnectorType.AMM_LP:
        return "Only AMM_LP connectors allowed."


def market_validator(value: str) -> None:
    connector = amm_v3_lp_config_map.get("connector").value
    return validate_market_trading_pair(connector, value)


def market_on_validated(value: str) -> None:
    connector = amm_v3_lp_config_map.get("connector").value
    requried_connector_trading_pairs[connector] = [value]


def market_prompt() -> str:
    connector = amm_v3_lp_config_map.get("connector").value
    example = AllConnectorSettings.get_example_pairs().get(connector)
    return "Enter the trading pair you would like to provide liquidity on {}>>> ".format(
        f"(e.g. {example}) " if example else "")


amm_v3_lp_config_map = {
    "strategy": ConfigVar(
        key="strategy",
        prompt="",
        default="amm_v3_lp"),
    "connector": ConfigVar(
        key="connector",
        prompt="Enter name of LP connector >>> ",
        validator=validate_connector,
        on_validated=exchange_on_validated,
        prompt_on_new=True),
    "market": ConfigVar(
        key="market",
        prompt=market_prompt,
        prompt_on_new=True,
        validator=market_validator,
        on_validated=market_on_validated),
    "fee_tier": ConfigVar(
        key="fee_tier",
        prompt="On which fee tier do you want to provide liquidity on? (LOWEST/LOW/MEDIUM/HIGH) ",
        validator=lambda s: None if s in {"LOWEST",
                                          "LOW",
                                          "MEDIUM",
                                          "HIGH",
                                          } else
        "Invalid fee tier.",
        prompt_on_new=True),
    "price_spread": ConfigVar(
        key="price_spread",
        prompt="How wide around current pool price and/or last created positions do you want new positions to span? (Enter 1 to indicate 1%)  >>> ",
        type_str="decimal",
        validator=lambda v: validate_decimal(v, Decimal("0"), inclusive=False),
        default=Decimal("1"),
        prompt_on_new=True),
    "amount": ConfigVar(
        key="amount",
        prompt="Enter the maximum value(in terms of base asset) to use for providing liquidity. >>>",
        prompt_on_new=True,
        validator=lambda v: validate_decimal(v, Decimal("0"), inclusive=False),
        type_str="decimal"),
    "min_profitability": ConfigVar(
        key="min_profitability",
        prompt="What is the minimum unclaimed fees an out of range position must have before it is closed? (in terms of base asset) >>>",
        prompt_on_new=False,
        validator=lambda v: validate_decimal(v, Decimal("0"), inclusive=False),
        default=Decimal("1"),
        type_str="decimal"),
}
