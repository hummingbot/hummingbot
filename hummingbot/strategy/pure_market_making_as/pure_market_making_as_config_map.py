from decimal import Decimal

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_market_trading_pair,
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
    exchange = pure_market_making_as_config_map.get("exchange").value
    example = EXAMPLE_PAIRS.get(exchange)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (exchange, f" (e.g. {example})" if example else "")


# strategy specific validators
def validate_exchange_trading_pair(value: str) -> Optional[str]:
    exchange = pure_market_making_as_config_map.get("exchange").value
    return validate_market_trading_pair(exchange, value)


async def order_amount_prompt() -> str:
    exchange = pure_market_making_as_config_map["exchange"].value
    trading_pair = pure_market_making_as_config_map["market"].value
    base_asset, quote_asset = trading_pair.split("-")
    min_amount = await minimum_order_amount(exchange, trading_pair)
    return f"What is the amount of {base_asset} per order? (minimum {min_amount}) >>> "


async def validate_order_amount(value: str) -> Optional[str]:
    try:
        exchange = pure_market_making_as_config_map["exchange"].value
        trading_pair = pure_market_making_as_config_map["market"].value
        min_amount = await minimum_order_amount(exchange, trading_pair)
        if Decimal(value) < min_amount:
            return f"Order amount must be at least {min_amount}."
    except Exception:
        return "Invalid order amount."


def on_validated_price_source_exchange(value: str):
    if value is None:
        pure_market_making_as_config_map["price_source_market"].value = None


def exchange_on_validated(value: str):
    required_exchanges.append(value)


def on_validated_parameters_based_on_spread(value: str):
    if value == 'True':
        pure_market_making_as_config_map.get("gamma").value = None
        pure_market_making_as_config_map.get("kappa").value = None
        pure_market_making_as_config_map.get("eta").value = None


pure_market_making_as_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt=None,
                  default="pure_market_making_as"),
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
                  default=True),
    "min_spread":
        ConfigVar(key="min_spread",
                  prompt="Enter the minimum spread allowed from mid-price in percentage "
                         "(Enter 1 to indicate 1%) >>> ",
                  type_str="decimal",
                  required_if=lambda: pure_market_making_as_config_map.get("parameters_based_on_spread").value,
                  validator=lambda v: validate_decimal(v, 0, 100, inclusive=False),
                  prompt_on_new=True),
    "max_spread":
        ConfigVar(key="max_spread",
                  prompt="Enter the maximum spread allowed from mid-price in percentage "
                         "(Enter 1 to indicate 1%) >>> ",
                  type_str="decimal",
                  required_if=lambda: pure_market_making_as_config_map.get("parameters_based_on_spread").value,
                  validator=lambda v: validate_decimal(v, 0, 100, inclusive=False),
                  prompt_on_new=True),
    "vol_to_spread_multiplier":
        ConfigVar(key="vol_to_spread_multiplier",
                  prompt="Enter the Volatility-to-Spread multiplier: "
                         "Beyond this number of sigmas, spreads will turn into multiples of volatility >>>",
                  type_str="decimal",
                  required_if=lambda: pure_market_making_as_config_map.get("parameters_based_on_spread").value,
                  validator=lambda v: validate_decimal(v, 0, 10, inclusive=False),
                  prompt_on_new=True),
    "inventory_risk_aversion":
        ConfigVar(key="inventory_risk_aversion",
                  prompt="Enter Inventory risk aversion: With 1.0 being extremely conservative about meeting inventory target, "
                         "at the expense of profit, and 0.0 for a profit driven, at the expense of inventory risk >>>",
                  type_str="decimal",
                  required_if=lambda: pure_market_making_as_config_map.get("parameters_based_on_spread").value,
                  validator=lambda v: validate_decimal(v, 0, 1, inclusive=False),
                  prompt_on_new=True),
    "kappa":
        ConfigVar(key="kappa",
                  prompt="Enter order book depth variable (kappa) >>> ",
                  type_str="decimal",
                  required_if=lambda: not pure_market_making_as_config_map.get("parameters_based_on_spread").value,
                  validator=lambda v: validate_decimal(v, 0, 1e10, inclusive=False),
                  prompt_on_new=True),
    "gamma":
        ConfigVar(key="gamma",
                  prompt="Enter risk factor (gamma) >>> ",
                  type_str="decimal",
                  required_if=lambda: not pure_market_making_as_config_map.get("parameters_based_on_spread").value,
                  validator=lambda v: validate_decimal(v, 0, 1e10, inclusive=False),
                  prompt_on_new=True),
    "eta":
        ConfigVar(key="eta",
                  prompt="Enter order amount shape factor (eta) >>> ",
                  type_str="decimal",
                  required_if=lambda: not pure_market_making_as_config_map.get("parameters_based_on_spread").value,
                  validator=lambda v: validate_decimal(v, 0, 1, inclusive=True),
                  prompt_on_new=True),
    "closing_time":
        ConfigVar(key="closing_time",
                  prompt="Enter algorithm closing time in days. "
                         "When this time is reached, spread equations will recycle t=0"
                         " (fractional quantities are allowed i.e. 1.27 days) >>> ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, 10, inclusive=False),
                  default=Decimal("1")),
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
                  default=Decimal("1800"),
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
                  prompt="What is your target base asset percentage? Enter 50 for 50% >>> ",
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
    "buffer_size":
        ConfigVar(key="buffer_size",
                  prompt="Enter amount of samples to use for volatility calculation>>> ",
                  type_str="int",
                  validator=lambda v: validate_decimal(v, 5, 600),
                  default=60),
    "buffer_sampling_period":
        ConfigVar(key="buffer_sampling_period",
                  prompt="Enter period in seconds of sampling for volatility calculation>>> ",
                  type_str="int",
                  validator=lambda v: validate_decimal(v, 1, 300),
                  default=1),
}
