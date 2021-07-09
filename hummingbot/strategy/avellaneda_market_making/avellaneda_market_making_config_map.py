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

# from hummingbot.strategy.hanging_orders_tracker import HangingOrdersAggregationType


def maker_trading_pair_prompt():
    exchange = avellaneda_market_making_config_map.get("exchange").value
    example = EXAMPLE_PAIRS.get(exchange)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (exchange, f" (e.g. {example})" if example else "")


# strategy specific validators
def validate_exchange_trading_pair(value: str) -> Optional[str]:
    exchange = avellaneda_market_making_config_map.get("exchange").value
    return validate_market_trading_pair(exchange, value)


def validate_max_spread(value: str) -> Optional[str]:
    is_invalid_decimal = validate_decimal(value, 0, 100, inclusive=False)
    if is_invalid_decimal:
        return is_invalid_decimal
    if avellaneda_market_making_config_map["min_spread"].value is not None:
        min_spread = Decimal(avellaneda_market_making_config_map["min_spread"].value)
        max_spread = Decimal(value)
        if min_spread >= max_spread:
            return f"Max spread cannot be lesser or equal to min spread {max_spread}%<={min_spread}%"


def onvalidated_min_spread(value: str):
    # If entered valid min_spread, max_spread is invalidated so user sets it up again
    avellaneda_market_making_config_map["max_spread"].value = None


async def order_amount_prompt() -> str:
    exchange = avellaneda_market_making_config_map["exchange"].value
    trading_pair = avellaneda_market_making_config_map["market"].value
    base_asset, quote_asset = trading_pair.split("-")
    min_amount = await minimum_order_amount(exchange, trading_pair)
    return f"What is the amount of {base_asset} per order? (minimum {min_amount}) >>> "


async def validate_order_amount(value: str) -> Optional[str]:
    try:
        exchange = avellaneda_market_making_config_map["exchange"].value
        trading_pair = avellaneda_market_making_config_map["market"].value
        min_amount = await minimum_order_amount(exchange, trading_pair)
        if Decimal(value) < min_amount:
            return f"Order amount must be at least {min_amount}."
    except Exception:
        return "Invalid order amount."


def on_validated_price_source_exchange(value: str):
    if value is None:
        avellaneda_market_making_config_map["price_source_market"].value = None


def exchange_on_validated(value: str):
    required_exchanges.append(value)


def on_validated_parameters_based_on_spread(value: str):
    if value == 'True':
        avellaneda_market_making_config_map.get("risk_factor").value = None
        avellaneda_market_making_config_map.get("order_book_depth_factor").value = None
        avellaneda_market_making_config_map.get("order_amount_shape_factor").value = None
    else:
        avellaneda_market_making_config_map.get("max_spread").value = None
        avellaneda_market_making_config_map.get("min_spread").value = None
        avellaneda_market_making_config_map.get("vol_to_spread_multiplier").value = None
        avellaneda_market_making_config_map.get("inventory_risk_aversion").value = None


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
    "order_amount":
        ConfigVar(key="order_amount",
                  prompt=order_amount_prompt,
                  type_str="decimal",
                  validator=validate_order_amount,
                  prompt_on_new=True),
    "order_optimization_enabled":
        ConfigVar(key="order_optimization_enabled",
                  prompt="Do you want to enable best bid ask jumping? (Yes/No) >>> ",
                  type_str="bool",
                  default=True,
                  validator=validate_bool),
    "parameters_based_on_spread":
        ConfigVar(key="parameters_based_on_spread",
                  prompt="Do you want to automate Avellaneda-Stoikov parameters based on min/max spread? >>> ",
                  type_str="bool",
                  validator=validate_bool,
                  on_validated=on_validated_parameters_based_on_spread,
                  default=True,
                  prompt_on_new=True),
    "min_spread":
        ConfigVar(key="min_spread",
                  prompt="Enter the minimum spread allowed from mid-price in percentage "
                         "(Enter 1 to indicate 1%) >>> ",
                  type_str="decimal",
                  required_if=lambda: avellaneda_market_making_config_map.get("parameters_based_on_spread").value,
                  validator=lambda v: validate_decimal(v, 0, 100, inclusive=False),
                  prompt_on_new=True,
                  on_validated=onvalidated_min_spread),
    "max_spread":
        ConfigVar(key="max_spread",
                  prompt="Enter the maximum spread allowed from mid-price in percentage "
                         "(Enter 1 to indicate 1%) >>> ",
                  type_str="decimal",
                  required_if=lambda: avellaneda_market_making_config_map.get("parameters_based_on_spread").value,
                  validator=lambda v: validate_max_spread(v),
                  prompt_on_new=True),
    "vol_to_spread_multiplier":
        ConfigVar(key="vol_to_spread_multiplier",
                  prompt="Enter the Volatility threshold multiplier: "
                         "(If market volatility multiplied by this value is above the minimum spread, "
                         "it will increase the minimum and maximum spread value) >>> ",
                  type_str="decimal",
                  required_if=lambda: avellaneda_market_making_config_map.get("parameters_based_on_spread").value,
                  validator=lambda v: validate_decimal(v, 0, 10, inclusive=True),
                  prompt_on_new=True),
    "volatility_sensibility":
        ConfigVar(key="volatility_sensibility",
                  prompt="Enter volatility change threshold to trigger parameter recalculation >>> ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, 100, inclusive=True),
                  default=20),
    "inventory_risk_aversion":
        ConfigVar(key="inventory_risk_aversion",
                  prompt="Enter Inventory risk aversion between 0 and 1: (For values close to 0.999 spreads will be more "
                         "skewed to meet the inventory target, while close to 0.001 spreads will be close to symmetrical, "
                         "increasing profitability but also increasing inventory risk) >>>",
                  type_str="decimal",
                  required_if=lambda: avellaneda_market_making_config_map.get("parameters_based_on_spread").value,
                  validator=lambda v: validate_decimal(v, 0, 1, inclusive=False),
                  prompt_on_new=True),
    "order_book_depth_factor":
        ConfigVar(key="order_book_depth_factor",
                  printable_key="order_book_depth_factor(\u03BA)",
                  prompt="Enter order book depth factor (\u03BA) >>> ",
                  type_str="decimal",
                  required_if=lambda: not avellaneda_market_making_config_map.get("parameters_based_on_spread").value,
                  validator=lambda v: validate_decimal(v, 0, 1e10, inclusive=False),
                  prompt_on_new=True),
    "risk_factor":
        ConfigVar(key="risk_factor",
                  printable_key="risk_factor(\u03B3)",
                  prompt="Enter risk factor (\u03B3) >>> ",
                  type_str="decimal",
                  required_if=lambda: not avellaneda_market_making_config_map.get("parameters_based_on_spread").value,
                  validator=lambda v: validate_decimal(v, 0, 1e10, inclusive=False),
                  prompt_on_new=True),
    "order_amount_shape_factor":
        ConfigVar(key="order_amount_shape_factor",
                  printable_key="order_amount_shape_factor(\u03B7)",
                  prompt="Enter order amount shape factor (\u03B7) >>> ",
                  type_str="decimal",
                  required_if=lambda: not avellaneda_market_making_config_map.get("parameters_based_on_spread").value,
                  validator=lambda v: validate_decimal(v, 0, 1, inclusive=True),
                  prompt_on_new=True),
    "closing_time":
        ConfigVar(key="closing_time",
                  prompt="Enter operational closing time (T). (How long will each trading cycle last "
                         "in days or fractions of day) >>> ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, 10, inclusive=False),
                  default=Decimal("0.041666667")),
    "order_refresh_time":
        ConfigVar(key="order_refresh_time",
                  prompt="How often do you want to cancel and replace bids and asks "
                         "(in seconds)? >>> ",
                  required_if=lambda: not (using_exchange("radar_relay")() or
                                           (using_exchange("bamboo_relay")() and not using_bamboo_coordinator_mode())),
                  type_str="float",
                  validator=lambda v: validate_decimal(v, 0, inclusive=False),
                  prompt_on_new=True),
    "max_order_age":
        ConfigVar(key="max_order_age",
                  prompt="How long do you want to cancel and replace bids and asks "
                         "with the same price (in seconds)? >>> ",
                  required_if=lambda: not (using_exchange("radar_relay")() or
                                           (using_exchange("bamboo_relay")() and not using_bamboo_coordinator_mode())),
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
                  validator=lambda v: validate_decimal(v, 5, 600),
                  default=60),
    "order_levels":
        ConfigVar(key="order_levels",
                  prompt="How many orders do you want to place on both sides? >>> ",
                  type_str="int",
                  validator=lambda v: validate_int(v, min_value=-1, inclusive=False),
                  default=1),
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
    # "hanging_orders_aggregation_type":
    #     ConfigVar(key="hanging_orders_aggregation_type",
    #               prompt="What kind of aggregation for the hanging orders? (no_aggregation/volume_weighted/volume_time_weighted/volume_distance_weighted) >>> ",
    #               type_str="str",
    #               default="no_aggregation",
    #               validator=lambda v: "Invalid option" if v.upper() not in [s.name for s in HangingOrdersAggregationType] else None,
    #               required_if=lambda: avellaneda_market_making_config_map.get("hanging_orders_enabled").value),
    "hanging_orders_cancel_pct":
        ConfigVar(key="hanging_orders_cancel_pct",
                  prompt="At what spread percentage (from mid price) will hanging orders be canceled? "
                         "(Enter 1 to indicate 1%) >>> ",
                  required_if=lambda: avellaneda_market_making_config_map.get("hanging_orders_enabled").value,
                  type_str="decimal",
                  default=Decimal("10"),
                  validator=lambda v: validate_decimal(v, 0, 100, inclusive=False)),
}
