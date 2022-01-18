from hummingbot.client import settings
from hummingbot.client.config.config_helpers import parse_cvar_value
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_market_trading_pair,
    validate_connector,
    validate_decimal,
    validate_bool
)
from hummingbot.client.settings import (
    required_exchanges,
    requried_connector_trading_pairs,
    AllConnectorSettings,
)
from decimal import Decimal


def exchange_on_validated(value: str) -> None:
    required_exchanges.append(value)


def market_1_validator(value: str) -> None:
    exchange = amm_arb_config_map["connector_1"].value
    return validate_market_trading_pair(exchange, value)


def market_1_on_validated(value: str) -> None:
    requried_connector_trading_pairs[amm_arb_config_map["connector_1"].value] = [value]


def market_2_validator(value: str) -> None:
    exchange = amm_arb_config_map["connector_2"].value
    return validate_market_trading_pair(exchange, value)


def market_2_on_validated(value: str) -> None:
    requried_connector_trading_pairs[amm_arb_config_map["connector_2"].value] = [value]


def market_1_prompt() -> str:
    connector = amm_arb_config_map.get("connector_1").value
    example = AllConnectorSettings.get_example_pairs().get(connector)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (connector, f" (e.g. {example})" if example else "")


def market_2_prompt() -> str:
    connector = amm_arb_config_map.get("connector_2").value
    example = AllConnectorSettings.get_example_pairs().get(connector)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (connector, f" (e.g. {example})" if example else "")


def order_amount_prompt() -> str:
    trading_pair = amm_arb_config_map["market_1"].value
    base_asset, quote_asset = trading_pair.split("-")
    return f"What is the amount of {base_asset} per order? >>> "


def update_oracle_settings(value: str):
    c_map = amm_arb_config_map
    if not (c_map["use_oracle_conversion_rate"].value is not None and
            c_map["market_1"].value is not None and
            c_map["market_2"].value is not None):
        return
    use_oracle = parse_cvar_value(c_map["use_oracle_conversion_rate"], c_map["use_oracle_conversion_rate"].value)
    first_base, first_quote = c_map["market_1"].value.split("-")
    second_base, second_quote = c_map["market_2"].value.split("-")
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


amm_arb_config_map = {
    "strategy": ConfigVar(
        key="strategy",
        prompt="",
        default="amm_arb"),
    "connector_1": ConfigVar(
        key="connector_1",
        prompt="Enter your first spot connector (Exchange/AMM) >>> ",
        prompt_on_new=True,
        validator=validate_connector,
        on_validated=exchange_on_validated),
    "market_1": ConfigVar(
        key="market_1",
        prompt=market_1_prompt,
        prompt_on_new=True,
        validator=market_1_validator,
        on_validated=market_1_on_validated),
    "connector_2": ConfigVar(
        key="connector_2",
        prompt="Enter your second spot connector (Exchange/AMM) >>> ",
        prompt_on_new=True,
        validator=validate_connector,
        on_validated=exchange_on_validated),
    "market_2": ConfigVar(
        key="market_2",
        prompt=market_2_prompt,
        prompt_on_new=True,
        validator=market_2_validator,
        on_validated=market_2_on_validated),
    "order_amount": ConfigVar(
        key="order_amount",
        prompt=order_amount_prompt,
        type_str="decimal",
        validator=lambda v: validate_decimal(v, Decimal("0")),
        prompt_on_new=True),
    "min_profitability": ConfigVar(
        key="min_profitability",
        prompt="What is the minimum profitability for you to make a trade? (Enter 1 to indicate 1%) >>> ",
        prompt_on_new=True,
        default=Decimal("1"),
        validator=lambda v: validate_decimal(v),
        type_str="decimal"),
    "market_1_slippage_buffer": ConfigVar(
        key="market_1_slippage_buffer",
        prompt="How much buffer do you want to add to the price to account for slippage for orders on the first market "
               "(Enter 1 for 1%)? >>> ",
        prompt_on_new=True,
        default=Decimal("0.05"),
        validator=lambda v: validate_decimal(v),
        type_str="decimal"),
    "market_2_slippage_buffer": ConfigVar(
        key="market_2_slippage_buffer",
        prompt="How much buffer do you want to add to the price to account for slippage for orders on the second market"
               " (Enter 1 for 1%)? >>> ",
        prompt_on_new=True,
        default=Decimal("0"),
        validator=lambda v: validate_decimal(v),
        type_str="decimal"),
    "concurrent_orders_submission": ConfigVar(
        key="concurrent_orders_submission",
        prompt="Do you want to submit both arb orders concurrently (Yes/No) ? If No, the bot will wait for first "
               "connector order filled before submitting the other order >>> ",
        prompt_on_new=True,
        default=False,
        validator=validate_bool,
        type_str="bool"),
    "use_oracle_conversion_rate": ConfigVar(
        key="use_oracle_conversion_rate",
        type_str="bool",
        prompt="Do you want to use rate oracle on unmatched trading pairs? (Yes/No) >>> ",
        prompt_on_new=True,
        validator=validate_bool,
        on_validated=update_oracle_settings,
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
