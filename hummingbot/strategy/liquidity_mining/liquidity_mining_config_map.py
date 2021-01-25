from decimal import Decimal
from typing import Optional
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_decimal
)
from hummingbot.client.settings import (
    required_exchanges,
)


def exchange_on_validated(value: str) -> None:
    required_exchanges.append(value)


def token_validate(value: str) -> Optional[str]:
    markets = list(liquidity_mining_config_map["markets"].value.split(","))
    tokens = set()
    for market in markets:
        tokens.update(set(market.split("-")))
    if value not in tokens:
        return f"Invalid token. {value} is not one of {','.join(tokens)}"


def order_size_prompt() -> str:
    token = liquidity_mining_config_map["token"].value
    return f"What is the size of each order (in {token} amount)? >>> "


def target_base_pct_prompt() -> str:
    markets = list(liquidity_mining_config_map["markets"].value.split(","))
    token = liquidity_mining_config_map["token"].value
    markets = [m for m in markets if token in m.split("-")]
    example = ",".join([f"{m}:10%" for m in markets[:2]])
    return f"For each of {token} markets, what is the target base asset pct? (Enter a list of markets and" \
           f" their target e.g. {example}) >>> "


liquidity_mining_config_map = {
    "strategy": ConfigVar(
        key="strategy",
        prompt="",
        default="liquidity_mining"),
    "exchange":
        ConfigVar(key="exchange",
                  prompt="Enter your liquidity mining exchange name >>> ",
                  validator=validate_exchange,
                  on_validated=exchange_on_validated,
                  prompt_on_new=True),
    "markets":
        ConfigVar(key="markets",
                  prompt="Enter a list of markets (comma separated, e.g. LTC-USDT,ETH-USDT) >>> ",
                  type_str="str",
                  prompt_on_new=True),
    "token":
        ConfigVar(key="token",
                  prompt="What asset (base or quote) do you want to use to provide liquidity? >>> ",
                  type_str="str",
                  validator=token_validate,
                  prompt_on_new=True),
    "order_size":
        ConfigVar(key="order_size",
                  prompt=order_size_prompt,
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, inclusive=False),
                  prompt_on_new=True),
    "spread":
        ConfigVar(key="spread",
                  prompt="How far away from the mid price do you want to place bid order and ask order? "
                         "(Enter 1 to indicate 1%) >>> ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, 100, inclusive=False),
                  prompt_on_new=True),
    "target_base_pct":
        ConfigVar(key="spread",
                  prompt=target_base_pct_prompt,
                  type_str="str",
                  prompt_on_new=True),
    "order_refresh_time":
        ConfigVar(key="order_refresh_time",
                  prompt="How often do you want to cancel and replace bids and asks "
                         "(in seconds)? >>> ",
                  type_str="float",
                  validator=lambda v: validate_decimal(v, 0, inclusive=False),
                  default=5.),
    "order_refresh_tolerance_pct":
        ConfigVar(key="order_refresh_tolerance_pct",
                  prompt="Enter the percent change in price needed to refresh orders at each cycle "
                         "(Enter 1 to indicate 1%) >>> ",
                  type_str="decimal",
                  default=Decimal("0.2"),
                  validator=lambda v: validate_decimal(v, -10, 10, inclusive=True)),

}
