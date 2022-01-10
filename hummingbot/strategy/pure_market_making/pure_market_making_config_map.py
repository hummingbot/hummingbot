from decimal import Decimal

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_market_trading_pair,
    validate_bool,
    validate_decimal,
    validate_int
)
from hummingbot.client.settings import (
    required_exchanges,
    AllConnectorSettings,
)
from typing import Optional


def maker_trading_pair_prompt():
    exchange = pure_market_making_config_map.get("exchange").value
    example = AllConnectorSettings.get_example_pairs().get(exchange)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (exchange, f" (e.g. {example})" if example else "")


# strategy specific validators
def validate_exchange_trading_pair(value: str) -> Optional[str]:
    exchange = pure_market_making_config_map.get("exchange").value
    return validate_market_trading_pair(exchange, value)


def order_amount_prompt() -> str:
    trading_pair = pure_market_making_config_map["market"].value
    base_asset, quote_asset = trading_pair.split("-")
    return f"What is the amount of {base_asset} per order? >>> "


def validate_price_source(value: str) -> Optional[str]:
    if value not in {"current_market", "external_market", "custom_api"}:
        return "Invalid price source type."


def on_validate_price_source(value: str):
    if value != "external_market":
        pure_market_making_config_map["price_source_exchange"].value = None
        pure_market_making_config_map["price_source_market"].value = None
        pure_market_making_config_map["take_if_crossed"].value = None
    if value != "custom_api":
        pure_market_making_config_map["price_source_custom_api"].value = None
    else:
        pure_market_making_config_map["price_type"].value = "custom"


def price_source_market_prompt() -> str:
    external_market = pure_market_making_config_map.get("price_source_exchange").value
    return f'Enter the token trading pair on {external_market} >>> '


def validate_price_source_exchange(value: str) -> Optional[str]:
    if value == pure_market_making_config_map.get("exchange").value:
        return "Price source exchange cannot be the same as maker exchange."
    return validate_exchange(value)


def on_validated_price_source_exchange(value: str):
    if value is None:
        pure_market_making_config_map["price_source_market"].value = None


def validate_price_source_market(value: str) -> Optional[str]:
    market = pure_market_making_config_map.get("price_source_exchange").value
    return validate_market_trading_pair(market, value)


def validate_price_floor_ceiling(value: str) -> Optional[str]:
    try:
        decimal_value = Decimal(value)
    except Exception:
        return f"{value} is not in decimal format."
    if not (decimal_value == Decimal("-1") or decimal_value > Decimal("0")):
        return "Value must be more than 0 or -1 to disable this feature."


def validate_price_type(value: str) -> Optional[str]:
    error = None
    price_source = pure_market_making_config_map.get("price_source").value
    if price_source != "custom_api":
        valid_values = {"mid_price",
                        "last_price",
                        "last_own_trade_price",
                        "best_bid",
                        "best_ask",
                        "inventory_cost",
                        }
        if value not in valid_values:
            error = "Invalid price type."
    elif value != "custom":
        error = "Invalid price type."
    return error


def on_validated_price_type(value: str):
    if value == 'inventory_cost':
        pure_market_making_config_map["inventory_price"].value = None


def exchange_on_validated(value: str):
    required_exchanges.append(value)


pure_market_making_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt=None,
                  default="pure_market_making"),
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
                  prompt_on_new=True,
                  validator=validate_bool),
    "order_levels":
        ConfigVar(key="order_levels",
                  prompt="How many orders do you want to place on both sides? >>> ",
                  type_str="int",
                  validator=lambda v: validate_int(v, min_value=-1, inclusive=False),
                  default=1),
    "order_level_amount":
        ConfigVar(key="order_level_amount",
                  prompt="How much do you want to increase or decrease the order size for each "
                         "additional order? (decrease < 0 > increase) >>> ",
                  required_if=lambda: pure_market_making_config_map.get("order_levels").value > 1,
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v),
                  default=0),
    "order_level_spread":
        ConfigVar(key="order_level_spread",
                  prompt="Enter the price increments (as percentage) for subsequent "
                         "orders? (Enter 1 to indicate 1%) >>> ",
                  required_if=lambda: pure_market_making_config_map.get("order_levels").value > 1,
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, 100, inclusive=False),
                  default=Decimal("1")),
    "inventory_skew_enabled":
        ConfigVar(key="inventory_skew_enabled",
                  prompt="Would you like to enable inventory skew? (Yes/No) >>> ",
                  type_str="bool",
                  default=False,
                  validator=validate_bool),
    "inventory_target_base_pct":
        ConfigVar(key="inventory_target_base_pct",
                  prompt="What is your target base asset percentage? Enter 50 for 50% >>> ",
                  required_if=lambda: pure_market_making_config_map.get("inventory_skew_enabled").value,
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, 100),
                  default=Decimal("50")),
    "inventory_range_multiplier":
        ConfigVar(key="inventory_range_multiplier",
                  prompt="What is your tolerable range of inventory around the target, "
                         "expressed in multiples of your total order size? ",
                  required_if=lambda: pure_market_making_config_map.get("inventory_skew_enabled").value,
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, min_value=0, inclusive=False),
                  default=Decimal("1")),
    "inventory_price":
        ConfigVar(key="inventory_price",
                  prompt="What is the price of your base asset inventory? ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, min_value=Decimal("0"), inclusive=True),
                  required_if=lambda: pure_market_making_config_map.get("price_type").value == "inventory_cost",
                  default=Decimal("1"),
                  ),
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
                  required_if=lambda: pure_market_making_config_map.get("hanging_orders_enabled").value,
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
                  required_if=lambda: pure_market_making_config_map.get("order_optimization_enabled").value,
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, min_value=0),
                  default=0),
    "bid_order_optimization_depth":
        ConfigVar(key="bid_order_optimization_depth",
                  prompt="How deep do you want to go into the order book for calculating "
                         "the top bid, ignoring dust orders on the top "
                         "(expressed in base asset amount)? >>> ",
                  required_if=lambda: pure_market_making_config_map.get("order_optimization_enabled").value,
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
                  prompt="Which price type to use? ("
                         "mid_price/last_price/last_own_trade_price/best_bid/best_ask/inventory_cost) >>> ",
                  type_str="str",
                  required_if=lambda: pure_market_making_config_map.get("price_source").value != "custom_api",
                  default="mid_price",
                  on_validated=on_validated_price_type,
                  validator=validate_price_type),
    "price_source_exchange":
        ConfigVar(key="price_source_exchange",
                  prompt="Enter external price source exchange name >>> ",
                  required_if=lambda: pure_market_making_config_map.get("price_source").value == "external_market",
                  type_str="str",
                  validator=validate_price_source_exchange,
                  on_validated=on_validated_price_source_exchange),
    "price_source_market":
        ConfigVar(key="price_source_market",
                  prompt=price_source_market_prompt,
                  required_if=lambda: pure_market_making_config_map.get("price_source").value == "external_market",
                  type_str="str",
                  validator=validate_price_source_market),
    "take_if_crossed":
        ConfigVar(key="take_if_crossed",
                  prompt="Do you want to take the best order if orders cross the orderbook? ((Yes/No) >>> ",
                  required_if=lambda: pure_market_making_config_map.get(
                      "price_source").value == "external_market",
                  type_str="bool",
                  validator=validate_bool),
    "price_source_custom_api":
        ConfigVar(key="price_source_custom_api",
                  prompt="Enter pricing API URL >>> ",
                  required_if=lambda: pure_market_making_config_map.get("price_source").value == "custom_api",
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
    "should_wait_order_cancel_confirmation":
        ConfigVar(key="should_wait_order_cancel_confirmation",
                  prompt="Should the strategy wait to receive a confirmation for orders cancellation "
                         "before creating a new set of orders? "
                         "(Not waiting requires enough available balance) (Yes/No) >>> ",
                  type_str="bool",
                  default=True,
                  validator=validate_bool),
}
