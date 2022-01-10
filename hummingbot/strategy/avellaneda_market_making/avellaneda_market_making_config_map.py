from decimal import Decimal

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_market_trading_pair,
    validate_int,
    validate_bool,
    validate_decimal,
    validate_datetime_iso_string,
    validate_time_iso_string,
)
from hummingbot.client.settings import (
    required_exchanges,
    AllConnectorSettings,
)
from typing import Optional


def maker_trading_pair_prompt():
    exchange = avellaneda_market_making_config_map.get("exchange").value
    example = AllConnectorSettings.get_example_pairs().get(exchange)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (exchange, f" (e.g. {example})" if example else "")


# strategy specific validators
def validate_exchange_trading_pair(value: str) -> Optional[str]:
    exchange = avellaneda_market_making_config_map.get("exchange").value
    return validate_market_trading_pair(exchange, value)


def validate_execution_timeframe(value: str) -> Optional[str]:
    timeframes = ["infinite", "from_date_to_date", "daily_between_times"]
    if value not in timeframes:
        return f"Invalid timeframe, please choose value from {timeframes}"


def validate_execution_time(value: str) -> Optional[str]:
    if avellaneda_market_making_config_map.get("execution_timeframe").value == "from_date_to_date":
        ret = validate_datetime_iso_string(value)
    if avellaneda_market_making_config_map.get("execution_timeframe").value == "daily_between_times":
        ret = validate_time_iso_string(value)
    if ret is not None:
        return ret


def execution_time_start_prompt() -> str:
    if avellaneda_market_making_config_map.get("execution_timeframe").value == "from_date_to_date":
        return "Please enter the start date and time (YYYY-MM-DD HH:MM:SS) >>> "
    if avellaneda_market_making_config_map.get("execution_timeframe").value == "daily_between_times":
        return "Please enter the start time (HH:MM:SS) >>> "


def execution_time_end_prompt() -> str:
    if avellaneda_market_making_config_map.get("execution_timeframe").value == "from_date_to_date":
        return "Please enter the end date and time (YYYY-MM-DD HH:MM:SS) >>> "
    if avellaneda_market_making_config_map.get("execution_timeframe").value == "daily_between_times":
        return "Please enter the end time (HH:MM:SS) >>> "


def on_validated_execution_timeframe(value: str):
    avellaneda_market_making_config_map["start_time"].value = None
    avellaneda_market_making_config_map["end_time"].value = None


def order_amount_prompt() -> str:
    trading_pair = avellaneda_market_making_config_map["market"].value
    base_asset, quote_asset = trading_pair.split("-")
    return f"What is the amount of {base_asset} per order? >>> "


def on_validated_price_source_exchange(value: str):
    if value is None:
        avellaneda_market_making_config_map["price_source_market"].value = None


def exchange_on_validated(value: str):
    required_exchanges.append(value)


avellaneda_market_making_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt=None,
                  default="avellaneda_market_making"),
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
    "execution_timeframe":
        ConfigVar(key="execution_timeframe",
                  prompt="Choose execution timeframe ( infinite / from_date_to_date / daily_between_times ) >>> ",
                  validator=validate_execution_timeframe,
                  on_validated=on_validated_execution_timeframe,
                  prompt_on_new=True),
    "start_time":
        ConfigVar(key="start_time",
                  prompt=execution_time_start_prompt,
                  type_str="str",
                  validator=validate_execution_time,
                  required_if=lambda: avellaneda_market_making_config_map.get("execution_timeframe").value != "infinite",
                  prompt_on_new=True),
    "end_time":
        ConfigVar(key="end_time",
                  prompt=execution_time_end_prompt,
                  type_str="str",
                  validator=validate_execution_time,
                  required_if=lambda: avellaneda_market_making_config_map.get("execution_timeframe").value != "infinite",
                  prompt_on_new=True),
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
                  default=True,
                  validator=validate_bool),
    "risk_factor":
        ConfigVar(key="risk_factor",
                  printable_key="risk_factor(\u03B3)",
                  prompt="Enter risk factor (\u03B3) >>> ",
                  type_str="decimal",
                  default=Decimal("1"),
                  validator=lambda v: validate_decimal(v, 0, inclusive=False),
                  prompt_on_new=True),
    "order_amount_shape_factor":
        ConfigVar(key="order_amount_shape_factor",
                  printable_key="order_amount_shape_factor(\u03B7)",
                  prompt="Enter order amount shape factor (\u03B7) >>> ",
                  type_str="decimal",
                  default=Decimal("0"),
                  validator=lambda v: validate_decimal(v, 0, 1, inclusive=True)),
    "min_spread":
        ConfigVar(key="min_spread",
                  prompt="Enter minimum spread limit (as % of mid price) >>> ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, inclusive=True),
                  default=Decimal("0")),
    "order_refresh_time":
        ConfigVar(key="order_refresh_time",
                  prompt="How often do you want to cancel and replace bids and asks "
                         "(in seconds)? >>> ",
                  type_str="float",
                  validator=lambda v: validate_decimal(v, 0, inclusive=False),
                  prompt_on_new=True),
    "max_order_age":
        ConfigVar(key="max_order_age",
                  prompt="How long do you want to cancel and replace bids and asks "
                         "with the same price (in seconds)? >>> ",
                  type_str="float",
                  default=1800,
                  validator=lambda v: validate_decimal(v, 0, inclusive=False)),
    "order_refresh_tolerance_pct":
        ConfigVar(key="order_refresh_tolerance_pct",
                  prompt="Enter the percent change in price needed to refresh orders at each cycle "
                         "(Enter 1 to indicate 1%) >>> ",
                  type_str="decimal",
                  default=Decimal("0"),
                  validator=lambda v: validate_decimal(v, -10, 10, inclusive=True)),
    "filled_order_delay":
        ConfigVar(key="filled_order_delay",
                  prompt="How long do you want to wait before placing the next order "
                         "if your order gets filled (in seconds)? >>> ",
                  type_str="float",
                  validator=lambda v: validate_decimal(v, min_value=0, inclusive=False),
                  default=60),
    "inventory_target_base_pct":
        ConfigVar(key="inventory_target_base_pct",
                  prompt="What is the inventory target for the base asset? Enter 50 for 50% >>> ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, 100),
                  prompt_on_new=True,
                  default=Decimal("50")),
    "add_transaction_costs":
        ConfigVar(key="add_transaction_costs",
                  prompt="Do you want to add transaction costs automatically to order prices? (Yes/No) >>> ",
                  type_str="bool",
                  default=False,
                  validator=validate_bool),
    "volatility_buffer_size":
        ConfigVar(key="volatility_buffer_size",
                  prompt="Enter amount of ticks that will be stored to calculate volatility >>> ",
                  type_str="int",
                  validator=lambda v: validate_decimal(v, 1, 10000),
                  default=200),
    "trading_intensity_buffer_size":
        ConfigVar(key="trading_intensity_buffer_size",
                  prompt="Enter amount of ticks that will be stored to estimate order book liquidity >>> ",
                  type_str="int",
                  validator=lambda v: validate_int(v, 1, 10000),
                  default=200),
    "order_levels":
        ConfigVar(key="order_levels",
                  prompt="How many orders do you want to place on both sides? >>> ",
                  type_str="int",
                  validator=lambda v: validate_int(v, min_value=-1, inclusive=False),
                  default=1),
    "level_distances":
        ConfigVar(key="level_distances",
                  prompt="How far apart in % of optimal spread should orders on one side be? >>> ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, min_value=0, inclusive=True),
                  default=0),
    "order_override":
        ConfigVar(key="order_override",
                  prompt=None,
                  required_if=lambda: False,
                  default=None,
                  type_str="json"),
    "hanging_orders_enabled":
        ConfigVar(key="hanging_orders_enabled",
                  prompt="Do you want to enable hanging orders? (Yes/No) >>> ",
                  type_str="bool",
                  default=False,
                  validator=validate_bool),
    "hanging_orders_cancel_pct":
        ConfigVar(key="hanging_orders_cancel_pct",
                  prompt="At what spread percentage (from mid price) will hanging orders be canceled? "
                         "(Enter 1 to indicate 1%) >>> ",
                  required_if=lambda: avellaneda_market_making_config_map.get("hanging_orders_enabled").value,
                  type_str="decimal",
                  default=Decimal("10"),
                  validator=lambda v: validate_decimal(v, 0, 100, inclusive=False)),
    "should_wait_order_cancel_confirmation":
        ConfigVar(key="should_wait_order_cancel_confirmation",
                  prompt="Should the strategy wait to receive a confirmation for orders cancellation "
                         "before creating a new set of orders? "
                         "(Not waiting requires enough available balance) (Yes/No) >>> ",
                  type_str="bool",
                  default=True,
                  validator=validate_bool),
}
