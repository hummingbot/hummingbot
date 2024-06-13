from decimal import Decimal

from hummingbot.client.config.config_validators import (
    validate_bool,
    validate_connector,
    validate_decimal,
    validate_int,
    validate_market_trading_pair,
)
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import AllConnectorSettings, required_exchanges, requried_connector_trading_pairs


def exchange_on_validated(value: str) -> None:
    required_exchanges.add(value)


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


amm_arb_config_map = {
    "strategy": ConfigVar(
        key="strategy",
        prompt="",
        default="amm_arb"),
    "connector_1": ConfigVar(
        key="connector_1",
        prompt="Enter your first connector (Exchange/AMM/CLOB) >>> ",
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
        prompt="Enter your second connector (Exchange/AMM/CLOB) >>> ",
        prompt_on_new=True,
        validator=validate_connector,
        on_validated=exchange_on_validated),
    "market_2": ConfigVar(
        key="market_2",
        prompt=market_2_prompt,
        prompt_on_new=True,
        validator=market_2_validator,
        on_validated=market_2_on_validated),
    "pool_id": ConfigVar(
        key="pool_id",
        prompt="Specify poolId to interract with on the DEX connector >>> ",
        prompt_on_new=False,
        type_str="str",
        default=""),
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
        default=lambda: Decimal(1) if amm_arb_config_map["connector_1"].value in sorted(
            AllConnectorSettings.get_gateway_amm_connector_names().union(
                AllConnectorSettings.get_gateway_clob_connector_names()
            )
        ) else Decimal(0),
        validator=lambda v: validate_decimal(v),
        type_str="decimal"),
    "market_2_slippage_buffer": ConfigVar(
        key="market_2_slippage_buffer",
        prompt="How much buffer do you want to add to the price to account for slippage for orders on the second market"
               " (Enter 1 for 1%)? >>> ",
        prompt_on_new=True,
        default=lambda: Decimal(1) if amm_arb_config_map["connector_2"].value in sorted(
            AllConnectorSettings.get_gateway_amm_connector_names().union(
                AllConnectorSettings.get_gateway_clob_connector_names()
            )
        ) else Decimal(0),
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
    "debug_price_shim": ConfigVar(
        key="debug_price_shim",
        prompt="Do you want to enable the debug price shim for integration tests? If you don't know what this does "
               "you should keep it disabled. >>> ",
        default=False,
        validator=validate_bool,
        type_str="bool"),
    "gateway_transaction_cancel_interval": ConfigVar(
        key="gateway_transaction_cancel_interval",
        prompt="After what time should blockchain transactions be cancelled if they are not included in a block? "
               "(this only affects decentralized exchanges) (Enter time in seconds) >>> ",
        default=600,
        validator=lambda v: validate_int(v, min_value=1, inclusive=True),
        type_str="int"),
    "rate_oracle_enabled": ConfigVar(
        key="rate_oracle_enabled",
        prompt="Do you want to use the rate oracle? (Yes/No) >>> ",
        default=True,
        validator=validate_bool,
        type_str="bool"),
    "quote_conversion_rate": ConfigVar(
        key="quote_conversion_rate",
        prompt="What is the fixed_rate used to convert quote assets? >>> ",
        default=Decimal("1"),
        validator=lambda v: validate_decimal(v),
        type_str="decimal"),
}
