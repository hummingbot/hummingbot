from decimal import Decimal
from typing import Optional

from hummingbot.client.config.config_validators import (
    validate_bool,
    validate_decimal,
    validate_exchange,
    validate_int,
    validate_market_trading_pair,
)
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import AllConnectorSettings, required_exchanges


def maker_trading_pair_prompt():
    exchange = fixed_grid_config_map.get("exchange").value
    example = AllConnectorSettings.get_example_pairs().get(exchange)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (exchange, f" (e.g. {example})" if example else "")


# strategy specific validators
def validate_exchange_trading_pair(value: str) -> Optional[str]:
    exchange = fixed_grid_config_map.get("exchange").value
    return validate_market_trading_pair(exchange, value)


def order_amount_prompt() -> str:
    trading_pair = fixed_grid_config_map["market"].value
    base_asset, quote_asset = trading_pair.split("-")
    return f"What is the amount of {base_asset} per order? >>> "


def validate_price_floor_ceiling(value: str) -> Optional[str]:
    try:
        decimal_value = Decimal(value)
    except Exception:
        return f"{value} is not in decimal format."
    if not (decimal_value == Decimal("-1") or decimal_value > Decimal("0")):
        return "Value must be more than 0 or -1 to disable this feature."


def exchange_on_validated(value: str):
    required_exchanges.add(value)


fixed_grid_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt=None,
                  default="fixed_grid"),
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
    "n_levels":
        ConfigVar(key="n_levels",
                  prompt="How many levels do you want on the fixed_grid? >>> ",
                  type_str="int",
                  validator=lambda v: validate_int(v, min_value=-1, inclusive=False),
                  default=5,
                  prompt_on_new=True),
    "grid_price_ceiling":
        ConfigVar(key="grid_price_ceiling",
                  prompt="Enter the ceiling price for the grid (top most order) >>>",
                  type_str="decimal",
                  validator=validate_price_floor_ceiling,
                  prompt_on_new=True),
    "grid_price_floor":
        ConfigVar(key="grid_price_floor",
                  prompt="Enter the floor price for the grid (bottom most order) >>>",
                  type_str="decimal",
                  validator=validate_price_floor_ceiling,
                  prompt_on_new=True),
    "start_order_spread":
        ConfigVar(key="start_order_spread",
                  prompt="How far away from the mid price do you want to place the "
                         "first order used to rebalance grid? (Enter 1 to indicate 1%) >>> ",
                  type_str="decimal",
                  default=Decimal("0.2"),
                  validator=lambda v: validate_decimal(v, 0, 100, inclusive=False)),
    "order_refresh_time":
        ConfigVar(key="order_refresh_time",
                  prompt="How often do you want to cancel and replace bids and asks "
                         "(in seconds)? >>> ",
                  type_str="float",
                  default=Decimal("1800"),
                  validator=lambda v: validate_decimal(v, 0, inclusive=False)),
    "max_order_age":
        ConfigVar(key="max_order_age",
                  prompt="How long do you want to cancel and replace bids and asks "
                         "with the same price (in seconds)? >>> ",
                  type_str="float",
                  default=Decimal("1800"),
                  validator=lambda v: validate_decimal(v, 0, inclusive=False)),
    "order_refresh_tolerance_pct":
        ConfigVar(key="order_refresh_tolerance_pct",
                  prompt="Enter the percent change in price needed to refresh orders at each cycle "
                         "(Enter 1 to indicate 1%) >>> ",
                  type_str="decimal",
                  default=Decimal("0"),
                  validator=lambda v: validate_decimal(v, -10, 10, inclusive=True)),
    "order_amount":
        ConfigVar(key="order_amount",
                  prompt=order_amount_prompt,
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, min_value=Decimal("0"), inclusive=False),
                  prompt_on_new=True),
    "order_optimization_enabled":
        ConfigVar(key="order_optimization_enabled",
                  prompt="Do you want to enable best bid ask jumping? (Yes/No) >>> ",
                  type_str="bool",
                  default=False,
                  validator=validate_bool),
    "ask_order_optimization_depth":
        ConfigVar(key="ask_order_optimization_depth",
                  prompt="How deep do you want to go into the order book for calculating "
                         "the top ask, ignoring dust orders on the top "
                         "(expressed in base asset amount)? >>> ",
                  required_if=lambda: fixed_grid_config_map.get("order_optimization_enabled").value,
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, min_value=0),
                  default=0),
    "bid_order_optimization_depth":
        ConfigVar(key="bid_order_optimization_depth",
                  prompt="How deep do you want to go into the order book for calculating "
                         "the top bid, ignoring dust orders on the top "
                         "(expressed in base asset amount)? >>> ",
                  required_if=lambda: fixed_grid_config_map.get("order_optimization_enabled").value,
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, min_value=0),
                  default=0),
    "take_if_crossed":
        ConfigVar(key="take_if_crossed",
                  prompt="Do you want to take the best order if orders cross the orderbook? ((Yes/No) >>> ",
                  default=True,
                  type_str="bool",
                  validator=validate_bool),
    "should_wait_order_cancel_confirmation":
        ConfigVar(key="should_wait_order_cancel_confirmation",
                  prompt="Should the strategy wait to receive a confirmation for orders cancellation "
                         "before creating a new set of orders? "
                         "(Not waiting requires enough available balance) (Yes/No) >>> ",
                  type_str="bool",
                  default=True,
                  validator=validate_bool),
}