from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_market_trading_pair,
    validate_decimal,
    validate_int,
    validate_bool
)
from hummingbot.client.settings import (
    required_exchanges,
    requried_connector_trading_pairs,
    AllConnectorSettings,
)
from decimal import Decimal


def market_validator(value: str) -> None:
    exchange = "uniswap_v3"
    return validate_market_trading_pair(exchange, value)


def market_on_validated(value: str) -> None:
    required_exchanges.append(value)
    requried_connector_trading_pairs["uniswap_v3"] = [value]


def market_prompt() -> str:
    connector = "uniswap_v3"
    example = AllConnectorSettings.get_example_pairs().get(connector)
    return "Enter the trading pair you would like to provide liquidity on {}>>> ".format(
        f"(e.g. {example}) " if example else "")


uniswap_v3_lp_config_map = {
    "strategy": ConfigVar(
        key="strategy",
        prompt="",
        default="uniswap_v3_lp"),
    "market": ConfigVar(
        key="market",
        prompt=market_prompt,
        prompt_on_new=True,
        validator=market_validator,
        on_validated=market_on_validated),
    "fee_tier": ConfigVar(
        key="fee_tier",
        prompt="On which fee tier do you want to provide liquidity on? (LOW/MEDIUM/HIGH) ",
        validator=lambda s: None if s in {"LOW",
                                          "MEDIUM",
                                          "HIGH",
                                          } else
        "Invalid fee tier.",
        prompt_on_new=True),
    "use_volatility": ConfigVar(
        key="use_volatility",
        type_str="bool",
        prompt="Do you want to use price volatility to adjust spreads? (Yes/No) >>> ",
        prompt_on_new=False,
        default=False,
        validator=validate_bool,
    ),
    "volatility_period": ConfigVar(
        key="volatility_period",
        type_str="int",
        prompt="Enter how long (in hours) do you want to use for price volatility calculation >>> ",
        required_if=lambda: uniswap_v3_lp_config_map.get("use_volatility").value,
        validator=lambda v: validate_int(v, 1),
        default=1,
        prompt_on_new=False
    ),
    "volatility_factor": ConfigVar(
        key="volatility_factor",
        type_str="decimal",
        prompt="Enter the multiplier applied to price volatility >>> ",
        required_if=lambda: uniswap_v3_lp_config_map.get("use_volatility").value,
        validator=lambda v: validate_decimal(v, Decimal("0"), inclusive=False),
        default=Decimal("1"),
        prompt_on_new=False
    ),
    "buy_spread": ConfigVar(
        key="buy_spread",
        prompt="How far away from the mid price do you want to place the buy position? (Enter 1 to indicate 1%)  >>> ",
        type_str="decimal",
        validator=lambda v: validate_decimal(v, Decimal("0"), inclusive=False),
        default=Decimal("1"),
        prompt_on_new=True),
    "sell_spread": ConfigVar(
        key="sell_spread",
        prompt="How far away from the mid price do you want to place the sell position? (Enter 1 to indicate 1%) >>> ",
        type_str="decimal",
        validator=lambda v: validate_decimal(v, Decimal("0"), inclusive=False),
        default=Decimal("1"),
        prompt_on_new=True),
    "base_token_amount": ConfigVar(
        key="base_token_amount",
        prompt="How much of your base token do you want to use for the buy position? >>>",
        prompt_on_new=True,
        validator=lambda v: validate_decimal(v, Decimal("0"), inclusive=False),
        type_str="decimal"),
    "quote_token_amount": ConfigVar(
        key="quote_token_amount",
        prompt="How much of your quote token do you want to use for the sell position? >>>",
        prompt_on_new=True,
        validator=lambda v: validate_decimal(v, Decimal("0"), inclusive=False),
        type_str="decimal"),
    "min_profitability": ConfigVar(
        key="min_profitability",
        prompt="What is the minimum profitability for each position is be adjusted? (Enter 1 to indicate 1%) >>>",
        prompt_on_new=False,
        validator=lambda v: validate_decimal(v, Decimal("0"), inclusive=False),
        default=Decimal("1"),
        type_str="decimal"),
}
