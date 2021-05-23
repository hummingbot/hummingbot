from decimal import Decimal

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_market_trading_pair,
    validate_int,
    validate_bool,
    validate_decimal,
)
from hummingbot.client.settings import (
    required_exchanges,
    EXAMPLE_PAIRS,
)
from hummingbot.client.config.global_config_map import (
    using_bamboo_coordinator_mode,
    using_exchange
)
from hummingbot.client.config.config_helpers import (
    minimum_order_amount,
)
from typing import Optional


def maker_trading_pair_prompt():
    exchange = bbo_config_map.get("exchange").value
    example = EXAMPLE_PAIRS.get(exchange)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (exchange, f" (e.g. {example})" if example else "")


# strategy specific validators
def validate_exchange_trading_pair(value: str) -> Optional[str]:
    exchange = bbo_config_map.get("exchange").value
    return validate_market_trading_pair(exchange, value)


async def order_amount_prompt() -> str:
    exchange = bbo_config_map["exchange"].value
    trading_pair = bbo_config_map["market"].value
    base_asset, quote_asset = trading_pair.split("-")
    min_amount = await minimum_order_amount(exchange, trading_pair)
    return f"What is the amount of {base_asset} per order? (minimum {min_amount}) >>> "


async def validate_order_amount(value: str) -> Optional[str]:
    try:
        exchange = bbo_config_map["exchange"].value
        trading_pair = bbo_config_map["market"].value
        min_amount = await minimum_order_amount(exchange, trading_pair)
        if Decimal(value) < min_amount:
            return f"Order amount must be at least {min_amount}."
    except Exception:
        return "Invalid order amount."


def on_validated_price_source_exchange(value: str):
    if value is None:
        bbo_config_map["price_source_market"].value = None


def exchange_on_validated(value: str):
    required_exchanges.append(value)


bbo_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt=None,
                  default="bbo"),
    "exchange":
        ConfigVar(key="exchange",
                  prompt="Enter your maker spot connector >>> ",
                  validator=validate_exchange,
                  on_validated=exchange_on_validated,
                  prompt_on_new=True),
    "market":
        ConfigVar(key="market",
                  prompt=maker_trading_pair_prompt,
                  validator=validate_exchange_trading_pair,
                  prompt_on_new=True),
    "order_amount":
        ConfigVar(key="order_amount",
                  prompt=order_amount_prompt,
                  type_str="decimal",
                  validator=validate_order_amount,
                  prompt_on_new=True),
    "volatility_days":
        ConfigVar(key="volatility_days",
                  prompt="Enter amount of daily candles that will be used to calculate the volatility >>> ",
                  type_str="int",
                  validator=lambda v: validate_decimal(v, 5, 600),
                  prompt_on_new=True,
                  default=100),
    "entry_band":
        ConfigVar(key="entry_band",
                  prompt="How many standard deviations above the mean should the entry price be >>> ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, 6),
                  prompt_on_new=True,
                  default=3),
    "exit_band":
        ConfigVar(key="exit_band",
                  prompt="How many standard deviations below the mean should the exit price be >>> ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, 6),
                  prompt_on_new=True,
                  default=1),
}
