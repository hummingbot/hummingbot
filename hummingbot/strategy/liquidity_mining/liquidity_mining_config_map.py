from decimal import Decimal

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_decimal,
)
from hummingbot.client.settings import (
    required_exchanges,
)


def exchange_on_validated(value: str) -> None:
    required_exchanges.append(value)


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
                  prompt="Enter a list of markets >>> ",
                  # validator=validate_exchange_trading_pair,
                  prompt_on_new=True),
    "initial_spread":
        ConfigVar(key="initial_spread",
                  prompt="How far away from the mid price do you want to place bid order and ask order? "
                         "(Enter 1 to indicate 1%) >>> ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, 100, inclusive=False),
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
