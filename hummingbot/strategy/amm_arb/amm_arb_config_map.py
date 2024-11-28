from decimal import Decimal

from hummingbot.client.config.config_validators import (
    validate_bool,
    validate_connector,
    validate_decimal,
    validate_int,
    validate_market_trading_pair,
)
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import required_exchanges


def exchange_on_validated(value: str) -> None:
    required_exchanges.add(value)


def order_amount_prompt() -> str:
    market_pair = amm_arb_config_map["market_pair"].value
    base_asset, quote_asset = market_pair.split("-") if market_pair else ["", ""]
    return f"What is the amount of {base_asset} per order? >>> "


def is_exchange_required(i: int) -> bool:
    """Helper function to check if an exchange configuration is required"""
    number = amm_arb_config_map["number_of_exchanges"].value
    return number is not None and number >= i


# Create a base config map with all possible exchanges (e.g., up to 5)
MAX_EXCHANGES = 6
base_config = {
    "strategy": ConfigVar(key="strategy", prompt="", default="amm_arb"),
    "number_of_exchanges": ConfigVar(
        key="number_of_exchanges",
        prompt="Enter the number of exchanges to perform arbitrage with >>> ",
        type_str="int",
        validator=lambda v: validate_int(v, min_value=2, max_value=MAX_EXCHANGES, inclusive=True),
        prompt_on_new=True,
    ),
}

# Add connector configs for maximum possible exchanges
for i in range(1, MAX_EXCHANGES + 1):
    base_config.update(
        {
            f"connector_{i}": ConfigVar(
                key=f"connector_{i}",
                prompt=f"Enter your connector {i} (Exchange/AMM/CLOB) >>> ",
                prompt_on_new=True,
                validator=validate_connector,
                on_validated=exchange_on_validated,
                required_if=lambda i=i: is_exchange_required(i),
            ),  # Pass i as default argument
            f"connector_{i}_slippage_buffer": ConfigVar(
                key=f"connector_{i}_slippage_buffer",
                prompt=f"How much buffer do you want to add to the price to account for slippage for orders on connector {i} "
                "(Enter 1 for 1%)? >>> ",
                prompt_on_new=True,
                default=Decimal("1"),
                validator=lambda v: validate_decimal(v),
                type_str="decimal",
                required_if=lambda i=i: is_exchange_required(i),
            ),  # Pass i as default argument
        }
    )

# Add remaining configs
remaining_config = {
    "market_pair": ConfigVar(
        key="market_pair",
        prompt="Enter the token trading pair you would like to trade >>> ",
        prompt_on_new=True,
        validator=lambda v: validate_market_trading_pair(amm_arb_config_map.get("connector_1").value, v),
        required_if=lambda: amm_arb_config_map["number_of_exchanges"].value is not None,
    ),  # Only required after number_of_exchanges is set
    "pool_id": ConfigVar(
        key="pool_id",
        prompt="Specify poolId to interact with on the DEX connector >>> ",
        prompt_on_new=False,
        type_str="str",
        default="",
    ),
    "order_amount": ConfigVar(
        key="order_amount",
        prompt=order_amount_prompt,
        type_str="decimal",
        validator=lambda v: validate_decimal(v, Decimal("0")),
        prompt_on_new=True,
    ),
    "min_profitability": ConfigVar(
        key="min_profitability",
        prompt="What is the minimum profitability for you to make a trade? (Enter 1 to indicate 1%) >>> ",
        prompt_on_new=True,
        default=Decimal("1"),
        validator=lambda v: validate_decimal(v),
        type_str="decimal",
    ),
    "concurrent_orders_submission": ConfigVar(
        key="concurrent_orders_submission",
        prompt="Do you want to submit both arb orders concurrently (Yes/No) ? If No, the bot will wait for first "
        "connector order filled before submitting the other order >>> ",
        prompt_on_new=True,
        default=False,
        validator=validate_bool,
        type_str="bool",
    ),
    "debug_price_shim": ConfigVar(
        key="debug_price_shim",
        prompt="Do you want to enable the debug price shim for integration tests? If you don't know what this does "
        "you should keep it disabled. >>> ",
        default=False,
        validator=validate_bool,
        type_str="bool",
    ),
    "gateway_transaction_cancel_interval": ConfigVar(
        key="gateway_transaction_cancel_interval",
        prompt="After what time should blockchain transactions be cancelled if they are not included in a block? "
        "(this only affects decentralized exchanges) (Enter time in seconds) >>> ",
        default=600,
        validator=lambda v: validate_int(v, min_value=1, inclusive=True),
        type_str="int",
    ),
    "rate_oracle_enabled": ConfigVar(
        key="rate_oracle_enabled",
        prompt="Do you want to use the rate oracle? (Yes/No) >>> ",
        default=True,
        validator=validate_bool,
        type_str="bool",
    ),
    "quote_conversion_rate": ConfigVar(
        key="quote_conversion_rate",
        prompt="What is the fixed_rate used to convert quote assets? >>> ",
        default=Decimal("1"),
        validator=lambda v: validate_decimal(v),
        type_str="decimal",
    ),
}

# Combine all configs
amm_arb_config_map = {**base_config, **remaining_config}
