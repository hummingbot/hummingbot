from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_market_trading_pair,
    validate_decimal
)
from hummingbot.client.settings import (
    required_exchanges,
    AllConnectorSettings,
)
from decimal import Decimal


def exchange_on_validated(value: str) -> None:
    required_exchanges.append(value)


def market_trading_pair_prompt() -> str:
    exchange = celo_arb_config_map.get("secondary_exchange").value
    example = AllConnectorSettings.get_example_pairs().get(exchange)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (exchange, f" (e.g. {example})" if example else "")


def order_amount_prompt() -> str:
    trading_pair = celo_arb_config_map["secondary_market"].value
    base_asset, quote_asset = trading_pair.split("-")
    return f"What is the amount of {base_asset} per order? >>> "


celo_arb_config_map = {
    "strategy": ConfigVar(
        key="strategy",
        prompt="",
        default="celo_arb"),
    "secondary_exchange": ConfigVar(
        key="secondary_exchange",
        prompt="Enter your secondary spot connector >>> ",
        prompt_on_new=True,
        validator=validate_exchange,
        on_validated=exchange_on_validated),
    "secondary_market": ConfigVar(
        key="secondary_market",
        prompt=market_trading_pair_prompt,
        prompt_on_new=True,
        validator=lambda x: validate_market_trading_pair(celo_arb_config_map["secondary_exchange"].value, x)),
    "order_amount": ConfigVar(
        key="order_amount",
        prompt=order_amount_prompt,
        type_str="decimal",
        prompt_on_new=True),
    "min_profitability": ConfigVar(
        key="min_profitability",
        prompt="What is the minimum profitability for you to make a trade? (Enter 1 to indicate 1%) >>> ",
        prompt_on_new=True,
        default=Decimal("0.3"),
        validator=lambda v: validate_decimal(v),
        type_str="decimal"),
    "celo_slippage_buffer": ConfigVar(
        key="celo_slippage_buffer",
        prompt="How much buffer do you want to add to the Celo price to account for slippage (Enter 1 for 1%)? >>> ",
        prompt_on_new=True,
        default=Decimal("0.01"),
        validator=lambda v: validate_decimal(v),
        type_str="decimal"),
}
