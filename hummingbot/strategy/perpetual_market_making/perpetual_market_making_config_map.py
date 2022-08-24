from decimal import Decimal
from typing import Optional

from hummingbot.client.config.config_validators import (
    validate_bool,
    validate_decimal,
    validate_derivative,
    validate_exchange,
    validate_int,
    validate_market_trading_pair,
)
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import AllConnectorSettings, required_exchanges


def maker_trading_pair_prompt():
    derivative = perpetual_market_making_config_map.get("derivative").value
    example = AllConnectorSettings.get_example_pairs().get(derivative)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (derivative, f" (e.g. {example})" if example else "")


# strategy specific validators
def validate_derivative_trading_pair(value: str) -> Optional[str]:
    derivative = perpetual_market_making_config_map.get("derivative").value
    return validate_market_trading_pair(derivative, value)


def validate_derivative_position_mode(value: str) -> Optional[str]:
    if value not in ["One-way", "Hedge"]:
        return "Position mode can either be One-way or Hedge mode"


def order_amount_prompt() -> str:
    trading_pair = perpetual_market_making_config_map["market"].value
    base_asset, quote_asset = trading_pair.split("-")
    return f"What is the amount of {base_asset} per order? >>> "


def validate_price_source(value: str) -> Optional[str]:
    if value not in {"current_market", "external_market", "custom_api"}:
        return "Invalid price source type."


def on_validate_price_source(value: str):
    if value != "external_market":
        perpetual_market_making_config_map["price_source_derivative"].value = None
        perpetual_market_making_config_map["price_source_market"].value = None
    if value != "custom_api":
        perpetual_market_making_config_map["price_source_custom_api"].value = None
    else:
        perpetual_market_making_config_map["price_type"].value = "custom"


def validate_price_type(value: str) -> Optional[str]:
    error = None
    price_source = perpetual_market_making_config_map.get("price_source").value
    if price_source != "custom_api":
        valid_values = {"mid_price",
                        "last_price",
                        "last_own_trade_price",
                        "best_bid",
                        "best_ask"}
        if value not in valid_values:
            error = "Invalid price type."
    elif value != "custom":
        error = "Invalid price type."
    return error


def price_source_market_prompt() -> str:
    external_market = perpetual_market_making_config_map.get("price_source_derivative").value
    return f'Enter the token trading pair on {external_market} >>> '


def validate_price_source_derivative(value: str) -> Optional[str]:
    if value == perpetual_market_making_config_map.get("derivative").value:
        return "Price source derivative cannot be the same as maker derivative."
    if validate_derivative(value) is not None and validate_exchange(value) is not None:
        return "Price source must must be a valid exchange or derivative connector."


def on_validated_price_source_derivative(value: str):
    if value is None:
        perpetual_market_making_config_map["price_source_market"].value = None


def validate_price_source_market(value: str) -> Optional[str]:
    market = perpetual_market_making_config_map.get("price_source_derivative").value
    return validate_market_trading_pair(market, value)


def validate_price_floor_ceiling(value: str) -> Optional[str]:
    try:
        decimal_value = Decimal(value)
    except Exception:
        return f"{value} is not in decimal format."
    if not (decimal_value == Decimal("-1") or decimal_value > Decimal("0")):
        return "Value must be more than 0 or -1 to disable this feature."


def derivative_on_validated(value: str):
    required_exchanges.add(value)


perpetual_market_making_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt=None,
                  default="perpetual_market_making"),
    "derivative":
        ConfigVar(key="derivative",
                  prompt="Enter your maker derivative connector exchange name >>> ",
                  validator=validate_derivative,
                  on_validated=derivative_on_validated,
                  prompt_on_new=True),
    "market":
        ConfigVar(key="market",
                  prompt=maker_trading_pair_prompt,
                  validator=validate_derivative_trading_pair,
                  prompt_on_new=True),
    "leverage":
        ConfigVar(key="leverage",
                  prompt="How much leverage do you want to use? "
                         "(Binance Perpetual supports up to 75X for most pairs) >>> ",
                  type_str="int",
                  validator=lambda v: validate_int(v, min_value=0, inclusive=False),
                  prompt_on_new=True),
    "position_mode":
        ConfigVar(key="position_mode",
                  prompt="Which position mode do you want to use? (One-way/Hedge) >>> ",
                  validator=validate_derivative_position_mode,
                  type_str="str",
                  default="One-way",
                  prompt_on_new=True),
    "bid_spread":
        ConfigVar(key="bid_spread",
                  prompt="How far away from the mid price do you want to place the "
                         "first bid order? (Enter 1 to indicate 1%) >>> ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, 100, inclusive=False),
                  prompt_on_new=True),
    "ask_spread":
        ConfigVar(key="ask_spread",
                  prompt="How far away from the mid price do you want to place the "
                         "first ask order? (Enter 1 to indicate 1%) >>> ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, 100, inclusive=False),
                  prompt_on_new=True),
    "minimum_spread":
        ConfigVar(key="minimum_spread",
                  prompt="At what minimum spread should the bot automatically cancel orders? (Enter 1 for 1%) >>> ",
                  required_if=lambda: False,
                  type_str="decimal",
                  default=Decimal(-100),
                  validator=lambda v: validate_decimal(v, -100, 100, True)),
    "order_refresh_time":
        ConfigVar(key="order_refresh_time",
                  prompt="How often do you want to cancel and replace bids and asks "
                         "(in seconds)? >>> ",
                  type_str="float",
                  validator=lambda v: validate_decimal(v, 0, inclusive=False),
                  prompt_on_new=True),
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
    "long_profit_taking_spread":
        ConfigVar(key="long_profit_taking_spread",
                  prompt="At what spread from the entry price do you want to place a short order to reduce position? (Enter 1 for 1%) >>> ",
                  type_str="decimal",
                  default=Decimal("0"),
                  validator=lambda v: validate_decimal(v, 0, 100, True),
                  prompt_on_new=True),
    "short_profit_taking_spread":
        ConfigVar(key="short_profit_taking_spread",
                  prompt="At what spread from the position entry price do you want to place a long order to reduce position? (Enter 1 for 1%) >>> ",
                  type_str="decimal",
                  default=Decimal("0"),
                  validator=lambda v: validate_decimal(v, 0, 100, True),
                  prompt_on_new=True),
    "stop_loss_spread":
        ConfigVar(key="stop_loss_spread",
                  prompt="At what spread from position entry price do you want to place stop_loss order? (Enter 1 for 1%) >>> ",
                  type_str="decimal",
                  default=Decimal("0"),
                  validator=lambda v: validate_decimal(v, 0, 101, False),
                  prompt_on_new=True),
    "time_between_stop_loss_orders":
        ConfigVar(key="time_between_stop_loss_orders",
                  prompt="How much time should pass before refreshing a stop loss order that has not been executed? (in seconds) >>> ",
                  type_str="float",
                  default=60,
                  validator=lambda v: validate_decimal(v, 0, inclusive=False),
                  prompt_on_new=True),
    "stop_loss_slippage_buffer":
        ConfigVar(key="stop_loss_slippage_buffer",
                  prompt="How much buffer should be added in stop loss orders' price to account for slippage? (Enter 1 for 1%)? >>> ",
                  type_str="decimal",
                  default=Decimal("0.5"),
                  validator=lambda v: validate_decimal(v, 0, inclusive=True),
                  prompt_on_new=True),
    "price_ceiling":
        ConfigVar(key="price_ceiling",
                  prompt="Enter the price point above which only sell orders will be placed "
                         "(Enter -1 to deactivate this feature) >>> ",
                  type_str="decimal",
                  default=Decimal("-1"),
                  validator=validate_price_floor_ceiling),
    "price_floor":
        ConfigVar(key="price_floor",
                  prompt="Enter the price below which only buy orders will be placed "
                         "(Enter -1 to deactivate this feature) >>> ",
                  type_str="decimal",
                  default=Decimal("-1"),
                  validator=validate_price_floor_ceiling),
    "order_levels":
        ConfigVar(key="order_levels",
                  prompt="How many orders do you want to place on both sides? >>> ",
                  type_str="int",
                  validator=lambda v: validate_int(v, min_value=0, inclusive=False),
                  default=1),
    "order_level_amount":
        ConfigVar(key="order_level_amount",
                  prompt="How much do you want to increase or decrease the order size for each "
                         "additional order? (decrease < 0 > increase) >>> ",
                  required_if=lambda: perpetual_market_making_config_map.get("order_levels").value > 1,
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v),
                  default=0),
    "order_level_spread":
        ConfigVar(key="order_level_spread",
                  prompt="Enter the price increments (as percentage) for subsequent "
                         "orders? (Enter 1 to indicate 1%) >>> ",
                  required_if=lambda: perpetual_market_making_config_map.get("order_levels").value > 1,
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, 100, inclusive=False),
                  default=Decimal("1")),
    "filled_order_delay":
        ConfigVar(key="filled_order_delay",
                  prompt="How long do you want to wait before placing the next order "
                         "if your order gets filled (in seconds)? >>> ",
                  type_str="float",
                  validator=lambda v: validate_decimal(v, min_value=0, inclusive=False),
                  default=60),
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
                  required_if=lambda: perpetual_market_making_config_map.get("order_optimization_enabled").value,
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, min_value=0),
                  default=0),
    "bid_order_optimization_depth":
        ConfigVar(key="bid_order_optimization_depth",
                  prompt="How deep do you want to go into the order book for calculating "
                         "the top bid, ignoring dust orders on the top "
                         "(expressed in base asset amount)? >>> ",
                  required_if=lambda: perpetual_market_making_config_map.get("order_optimization_enabled").value,
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, min_value=0),
                  default=0),
    "price_source":
        ConfigVar(key="price_source",
                  prompt="Which price source to use? (current_market/external_market/custom_api) >>> ",
                  type_str="str",
                  default="current_market",
                  validator=validate_price_source,
                  on_validated=on_validate_price_source),
    "price_type":
        ConfigVar(key="price_type",
                  prompt="Which price type to use? (mid_price/last_price/last_own_trade_price/best_bid/best_ask) >>> ",
                  type_str="str",
                  required_if=lambda: perpetual_market_making_config_map.get("price_source").value != "custom_api",
                  default="mid_price",
                  validator=validate_price_type),
    "price_source_derivative":
        ConfigVar(key="price_source_derivative",
                  prompt="Enter external price source connector name or derivative name >>> ",
                  required_if=lambda: perpetual_market_making_config_map.get("price_source").value == "external_market",
                  type_str="str",
                  validator=validate_price_source_derivative,
                  on_validated=on_validated_price_source_derivative),
    "price_source_market":
        ConfigVar(key="price_source_market",
                  prompt=price_source_market_prompt,
                  required_if=lambda: perpetual_market_making_config_map.get("price_source").value == "external_market",
                  type_str="str",
                  validator=validate_price_source_market),
    "price_source_custom_api":
        ConfigVar(key="price_source_custom_api",
                  prompt="Enter pricing API URL >>> ",
                  required_if=lambda: perpetual_market_making_config_map.get("price_source").value == "custom_api",
                  type_str="str"),
    "custom_api_update_interval":
        ConfigVar(key="custom_api_update_interval",
                  prompt="Enter custom API update interval in second (default: 5.0, min: 0.5) >>> ",
                  required_if=lambda: False,
                  default=float(5),
                  type_str="float",
                  validator=lambda v: validate_decimal(v, Decimal("0.5"))),
    "order_override":
        ConfigVar(key="order_override",
                  prompt=None,
                  required_if=lambda: False,
                  default=None,
                  type_str="json"),
}
