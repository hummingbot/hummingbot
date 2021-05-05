from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_market_trading_pair,
    validate_decimal,
)
from hummingbot.client.settings import (
    required_exchanges,
    requried_connector_trading_pairs,
    EXAMPLE_PAIRS,
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
    example = EXAMPLE_PAIRS.get(connector)
    return "Enter the pair you would like to provide liquidity to {}>>> ".format(
        f" (e.g. {example}) " if example else "")


def token_amount_prompt() -> str:
    trading_pair = uniswap_v3_lp_config_map["market"].value
    base_asset, quote_asset = trading_pair.split("-")
    return f"How much liquidity in {base_asset} do you want to provide for each position range? >>> "


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
    "buy_position_spread": ConfigVar(
        key="buy_position_spread",
        prompt="What spread from the current price do you want the buy position's lower price tick begin from? (Enter 1 to indicate 1%) >>> ",
        type_str="decimal",
        validator=lambda v: validate_decimal(v, Decimal("0")),
        prompt_on_new=True),
    "sell_position_spread": ConfigVar(
        key="sell_position_spread",
        prompt="What spread from the current price do you want the sell position's upper price tick end at? (Enter 1 to indicate 1%) >>> ",
        type_str="decimal",
        validator=lambda v: validate_decimal(v, Decimal("0")),
        prompt_on_new=True),
    "buy_position_price_spread": ConfigVar(
        key="buy_position_spread",
        prompt="How wide apart(in percentage) do you want the lower price to be from the upper price for buy position?(Enter 1 to indicate 1%)  >>> ",
        type_str="decimal",
        validator=lambda v: validate_decimal(v, Decimal("0")),
        prompt_on_new=True),
    "sell_position_price_spread": ConfigVar(
        key="sell_position_spread",
        prompt="How wide apart(in percentage) do you want the lower price to be from the upper price for sell position? (Enter 1 to indicate 1%) >>> ",
        type_str="decimal",
        validator=lambda v: validate_decimal(v, Decimal("0")),
        prompt_on_new=True),
    "token_amount": ConfigVar(
        key="token_amount",
        prompt=token_amount_prompt,
        prompt_on_new=True,
        validator=lambda v: validate_decimal(v, Decimal("0")),
        type_str="decimal"),
}
