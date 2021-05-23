from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_decimal,
    validate_bool
)
from hummingbot.client.settings import (
    required_exchanges,
)
from decimal import Decimal


def exchange_on_validated(value: str) -> None:
    required_exchanges.append(value)


def order_amount_prompt() -> str:
    trading_pair = amm_arb_config_map["market_list"].value[0][1]
    base_asset, quote_asset = trading_pair.split("-")
    return f"What is the amount of {base_asset} per order? >>> "


amm_arb_config_map = {
    "strategy": ConfigVar(
        key="strategy",
        prompt="",
        default="amm_arb"),
    "market_list": ConfigVar(
        key="market_list",
        prompt="",
        prompt_on_new=True),
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
    "concurrent_orders_submission": ConfigVar(
        key="concurrent_orders_submission",
        prompt="Do you want to submit both arb orders concurrently (Yes/No) ? If No, the bot will wait for first "
               "connector order filled before submitting the other order >>> ",
        prompt_on_new=True,
        default=False,
        validator=validate_bool,
        type_str="bool"),
}
