from decimal import Decimal

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_derivative,
    validate_market_trading_pair,
    validate_bool,
    validate_decimal,
    validate_int
)
from hummingbot.client.settings import (
    required_exchanges,
    EXAMPLE_PAIRS,
)

from hummingbot.client.config.config_helpers import (
    minimum_order_amount,
    parse_cvar_value
)
from typing import Optional


def maker_trading_pair_prompt():
    derivative = perpetual_market_making_config_map.get("derivative").value
    example = EXAMPLE_PAIRS.get(derivative)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (derivative, f" (e.g. {example})" if example else "")


# strategy specific validators
def validate_derivative_trading_pair(value: str) -> Optional[str]:
    derivative = perpetual_market_making_config_map.get("derivative").value
    return validate_market_trading_pair(derivative, value)


def validate_derivative_position_mode(value: str) -> Optional[str]:
    if value not in ["One-way", "Hedge"]:
        return "Position mode can either be One-way or Hedge mode"


async def order_amount_prompt() -> str:
    derivative = perpetual_market_making_config_map["derivative"].value
    trading_pair = perpetual_market_making_config_map["market"].value
    base_asset, quote_asset = trading_pair.split("-")
    min_amount = await minimum_order_amount(derivative, trading_pair)
    return f"What is the amount of {base_asset} per order? (minimum {min_amount}) >>> "


async def validate_order_amount(value: str) -> Optional[str]:
    try:
        derivative = perpetual_market_making_config_map["derivative"].value
        trading_pair = perpetual_market_making_config_map["market"].value
        min_amount = await minimum_order_amount(derivative, trading_pair)
        if Decimal(value) < min_amount:
            return f"Order amount must be at least {min_amount}."
    except Exception:
        return "Invalid order amount."


def validate_price_source(value: str) -> Optional[str]:
    if value not in {"current_market", "external_market", "custom_api"}:
        return "Invalid price source type."


def on_validate_price_source(value: str):
    if value != "external_market":
        perpetual_market_making_config_map["price_source_derivative"].value = None
        perpetual_market_making_config_map["price_source_market"].value = None
        perpetual_market_making_config_map["take_if_crossed"].value = None
    if value != "custom_api":
        perpetual_market_making_config_map["price_source_custom_api"].value = None
    else:
        perpetual_market_making_config_map["price_type"].value = None


def price_source_market_prompt() -> str:
    external_market = perpetual_market_making_config_map.get("price_source_derivative").value
    return f'Enter the token trading pair on {external_market} >>> '


def validate_price_source_derivative(value: str) -> Optional[str]:
    if value == perpetual_market_making_config_map.get("derivative").value:
        return "Price source derivative cannot be the same as maker derivative."
    if validate_derivative(value) is not None and validate_exchange(value) is not None:
        return "Price must must be a valid exchange or derivative connector."


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


def validate_take_if_crossed(value: str) -> Optional[str]:
    err_msg = validate_bool(value)
    if err_msg is not None:
        return err_msg
    price_source_enabled = perpetual_market_making_config_map["price_source_enabled"].value
    take_if_crossed = parse_cvar_value(perpetual_market_making_config_map["take_if_crossed"], value)
    if take_if_crossed and not price_source_enabled:
        return "You can enable this feature only when external pricing source for mid-market price is used."


def derivative_on_validated(value: str):
    required_exchanges.append(value)


perpetual_market_making_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt=None,
                  default="perpetual_market_making"),
    "derivative":
        ConfigVar(key="derivative",
                  prompt="Enter your maker derivative connector >>> ",
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
                  validator=validate_order_amount,
                  prompt_on_new=True),
    "position_management":
        ConfigVar(key="position_management",
                  prompt="How would you like to manage your positions? (Profit_taking/Trailing_stop) >>> ",
                  type_str="str",
                  default="Profit_taking",
                  validator=lambda s: None if s in {"Profit_taking", "Trailing_stop"} else
                  "Invalid position management.",
                  prompt_on_new=True),
    "long_profit_taking_spread":
        ConfigVar(key="long_profit_taking_spread",
                  prompt="At what spread from the entry price do you want to place a short order to reduce position? (Enter 1 for 1%) >>> ",
                  required_if=lambda: perpetual_market_making_config_map.get("position_management").value == "Profit_taking",
                  type_str="decimal",
                  default=Decimal("0"),
                  validator=lambda v: validate_decimal(v, 0, 100, True),
                  prompt_on_new=True),
    "short_profit_taking_spread":
        ConfigVar(key="short_profit_taking_spread",
                  prompt="At what spread from the position entry price do you want to place a long order to reduce position? (Enter 1 for 1%) >>> ",
                  required_if=lambda: perpetual_market_making_config_map.get("position_management").value == "Profit_taking",
                  type_str="decimal",
                  default=Decimal("0"),
                  validator=lambda v: validate_decimal(v, 0, 100, True),
                  prompt_on_new=True),
    "ts_activation_spread":
        ConfigVar(key="ts_activation_spread",
                  prompt="At what spread from the position entry price do you want the bot to start trailing? (Enter 1 for 1%) >>> ",
                  required_if=lambda: perpetual_market_making_config_map.get("position_management").value == "Trailing_stop",
                  type_str="decimal",
                  default=Decimal("0"),
                  validator=lambda v: validate_decimal(v, 0, 100, True),
                  prompt_on_new=True),
    "ts_callback_rate":
        ConfigVar(key="ts_callback_rate",
                  prompt="At what spread away from the trailing peak price do you want positions to remain open before they're closed? (Enter 1 for 1%) >>> ",
                  required_if=lambda: perpetual_market_making_config_map.get("position_management").value == "Trailing_stop",
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
    "close_position_order_type":
        ConfigVar(key="close_position_order_type",
                  prompt="What order type do you want trailing stop and/or stop loss features to use for closing positions? (LIMIT/MARKET) >>> ",
                  type_str="str",
                  default="LIMIT",
                  validator=lambda s: None if s in {"LIMIT", "MARKET"} else
                  "Invalid order type.",
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
    "ping_pong_enabled":
        ConfigVar(key="ping_pong_enabled",
                  prompt="Would you like to use the ping pong feature and alternate between buy and sell orders after fills? (Yes/No) >>> ",
                  type_str="bool",
                  default=False,
                  validator=validate_bool),
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
                  required_if=lambda: perpetual_market_making_config_map.get("hanging_orders_enabled").value,
                  type_str="decimal",
                  default=Decimal("10"),
                  validator=lambda v: validate_decimal(v, 0, 100, inclusive=False)),
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
    "add_transaction_costs":
        ConfigVar(key="add_transaction_costs",
                  prompt="Do you want to add transaction costs automatically to order prices? (Yes/No) >>> ",
                  type_str="bool",
                  default=False,
                  validator=validate_bool),
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
                  validator=lambda s: None if s in {"mid_price",
                                                    "last_price",
                                                    "last_own_trade_price",
                                                    "best_bid",
                                                    "best_ask"} else
                  "Invalid price type."),
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
    "take_if_crossed":
        ConfigVar(key="take_if_crossed",
                  prompt="Do you want to take the best order if orders cross the orderbook? (Yes/No) >>> ",
                  required_if=lambda: perpetual_market_making_config_map.get(
                      "price_source").value == "external_market",
                  type_str="bool",
                  validator=validate_bool),
    "price_source_custom_api":
        ConfigVar(key="price_source_custom_api",
                  prompt="Enter pricing API URL >>> ",
                  required_if=lambda: perpetual_market_making_config_map.get("price_source").value == "custom_api",
                  type_str="str"),
    "order_override":
        ConfigVar(key="order_override",
                  prompt=None,
                  required_if=lambda: False,
                  default=None,
                  type_str="json"),
}
