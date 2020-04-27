from decimal import Decimal

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_market_trading_pair,
    validate_bool,
    validate_decimal
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
    minimum_order_amount
)
from hummingbot.data_feed.exchange_price_manager import ExchangePriceManager
from typing import Optional


def maker_trading_pair_prompt():
    exchange = pure_market_making_config_map.get("exchange").value
    example = EXAMPLE_PAIRS.get(exchange)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (exchange, f" (e.g. {example})" if example else "")


# strategy specific validators
def validate_exchange_trading_pair(value: str) -> Optional[str]:
    exchange = pure_market_making_config_map.get("exchange").value
    return validate_market_trading_pair(exchange, value)


def order_amount_prompt() -> str:
    trading_pair = pure_market_making_config_map["market"].value
    base_asset, quote_asset = trading_pair.split("-")
    min_amount = minimum_order_amount(trading_pair)
    return f"What is the amount of {base_asset} per order? (minimum {min_amount}) >>> "


def order_start_size_prompt() -> str:
    trading_pair = pure_market_making_config_map["market"].value
    min_amount = minimum_order_amount(trading_pair)
    return f"What is the size of the first bid and ask order? (minimum {min_amount}) >>> "


def validate_order_amount(value: str) -> Optional[str]:
    try:
        trading_pair = pure_market_making_config_map["market"].value
        min_amount = minimum_order_amount(trading_pair)
        if Decimal(value) < min_amount:
            return f"Order amount must be at least {min_amount}."
    except Exception:
        return f"Invalid order amount."


def price_source_market_prompt():
    external_market = pure_market_making_config_map.get("price_source_exchange").value
    return f'Enter the token trading pair on {external_market} >>> '


def validate_price_source_exchange(value: str) -> Optional[str]:
    if value == pure_market_making_config_map.get("exchange").value:
        return "Price source exchange cannot be the same as maker exchange."
    return validate_exchange(value)


def validate_price_source_market(value: str) -> Optional[str]:
    market = pure_market_making_config_map.get("price_source_exchange").value
    return validate_market_trading_pair(market, value)


def exchange_on_validated(value: str):
    required_exchanges.append(value)
    ExchangePriceManager.set_exchanges_to_feed([value])
    ExchangePriceManager.start()


pure_market_making_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt=None,
                  default="pure_market_making"),
    "exchange":
        ConfigVar(key="exchange",
                  prompt="Enter your maker exchange name >>> ",
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
    "order_refresh_time":
        ConfigVar(key="order_refresh_time",
                  prompt="How often do you want to cancel and replace bids and asks "
                         "(in seconds)? >>> ",
                  required_if=lambda: not (using_exchange("radar_relay")() or
                                           (using_exchange("bamboo_relay")() and not using_bamboo_coordinator_mode())),
                  type_str="float",
                  validator=lambda v: validate_decimal(v, 0, inclusive=False),
                  prompt_on_new=True),
    "order_amount":
        ConfigVar(key="order_amount",
                  prompt=order_amount_prompt,
                  type_str="decimal",
                  validator=validate_order_amount,
                  prompt_on_new=True),
    "order_expiration_time":
        ConfigVar(key="order_expiration_time",
                  prompt="How long should your limit orders remain valid until they "
                         "expire and are replaced? (Minimum / Default is 130 seconds) >>> ",
                  default=130.0,
                  required_if=lambda: using_exchange("radar_relay")() or (using_exchange("bamboo_relay")() and
                                                                          not using_bamboo_coordinator_mode()),
                  type_str="float",
                  validator=lambda v: validate_decimal(v, 130)),
    "order_levels":
        ConfigVar(key="order_levels",
                  prompt="How many orders do you want to place on both sides? >>> ",
                  type_str="int",
                  default=1),
    "order_level_amount":
        ConfigVar(key="order_level_amount",
                  prompt="How much do you want to increase the order size for each "
                         "additional order? >>> ",
                  required_if=lambda: pure_market_making_config_map.get("order_levels").value > 1,
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, min_value=0),
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
                  validator=lambda v: validate_decimal(v, 0, 100)
                  ),
    "inventory_range_multiplier":
        ConfigVar(key="inventory_range_multiplier",
                  prompt="What is your tolerable range of inventory around the target, "
                         "expressed in multiples of your total order size? ",
                  required_if=lambda: pure_market_making_config_map.get("inventory_skew_enabled").value,
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, min_value=0, inclusive=False),
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
    "order_optimization_depth":
        ConfigVar(key="order_optimization_depth",
                  prompt="How deep do you want to go into the order book for calculating "
                         "the top bid and ask, ignoring dust orders on the top "
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
    "price_source_enabled": ConfigVar(key="price_source_enabled",
                                      prompt="Would you like to use an external pricing source for mid-market "
                                             "price? (Yes/No) >>> ",
                                      type_str="bool",
                                      default=False,
                                      validator=validate_bool),
    "price_source_type": ConfigVar(key="price_source_type",
                                   prompt="Which type of external price source to use? "
                                          "(exchange/custom_api) >>> ",
                                   required_if=lambda: pure_market_making_config_map.get(
                                       "price_source_enabled").value,
                                   type_str="str",
                                   validator=lambda s: None if s in {"exchange", "custom_api"} else
                                   "Invalid price source type."),
    "price_source_exchange": ConfigVar(key="price_source_exchange",
                                       prompt="Enter external price source exchange name >>> ",
                                       required_if=lambda: pure_market_making_config_map.get(
                                           "price_source_type").value == "exchange",
                                       type_str="str",
                                       validator=validate_price_source_exchange),
    "price_source_market": ConfigVar(key="price_source_market",
                                     prompt=price_source_market_prompt,
                                     required_if=lambda: pure_market_making_config_map.get(
                                         "price_source_type").value == "exchange",
                                     type_str="str",
                                     validator=validate_price_source_market),
    "price_source_custom": ConfigVar(key="price_source_custom",
                                     prompt="Enter pricing API URL >>> ",
                                     required_if=lambda: pure_market_making_config_map.get(
                                         "price_source_type").value == "custom_api",
                                     type_str="str")
}
