from decimal import Decimal

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_bool,
    validate_exchange,
    validate_market_trading_pair, validate_datetime_iso_string, validate_decimal,
)
from hummingbot.client.settings import (
    required_exchanges,
    AllConnectorSettings,
)
from typing import Optional
import math
from datetime import datetime


def trading_pair_prompt():
    exchange = twap_config_map.get("connector").value
    example = AllConnectorSettings.get_example_pairs().get(exchange)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (exchange, f" (e.g. {example})" if example else "")


def target_asset_amount_prompt():
    trading_pair = twap_config_map.get("trading_pair").value
    base_token, _ = trading_pair.split("-")

    return f"What is the total amount of {base_token} to be traded? (Default is 1.0) >>> "


def str2bool(value: str):
    return str(value).lower() in ("yes", "y", "true", "t", "1")


# checks if the trading pair is valid
def validate_market_trading_pair_tuple(value: str) -> Optional[str]:
    exchange = twap_config_map.get("connector").value
    return validate_market_trading_pair(exchange, value)


def set_order_delay_default(value: str = None):
    start_datetime_string = twap_config_map.get("start_datetime").value
    end_datetime_string = twap_config_map.get("end_datetime").value
    start_datetime = datetime.fromisoformat(start_datetime_string)
    end_datetime = datetime.fromisoformat(end_datetime_string)

    target_asset_amount = twap_config_map.get("target_asset_amount").value
    order_step_size = twap_config_map.get("order_step_size").value

    default = math.floor((end_datetime - start_datetime).total_seconds() / math.ceil(target_asset_amount / order_step_size))
    twap_config_map.get("order_delay_time").default = default


def validate_order_step_size(value: str = None):
    """
    Invalidates non-decimal input and checks if order_step_size is less than the target_asset_amount value
    :param value: User input for order_step_size parameter
    :return: Error message printed in output pane
    """
    result = validate_decimal(value, min_value=Decimal("0"), inclusive=False)
    if result is not None:
        return result
    target_asset_amount = twap_config_map.get("target_asset_amount").value
    if Decimal(value) > target_asset_amount:
        return "Order step size cannot be greater than the total trade amount."


twap_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt=None,
                  default="twap"),
    "connector":
        ConfigVar(key="connector",
                  prompt="Enter the name of spot connector >>> ",
                  validator=validate_exchange,
                  on_validated=lambda value: required_exchanges.append(value),
                  prompt_on_new=True),
    "trading_pair":
        ConfigVar(key="trading_pair",
                  prompt=trading_pair_prompt,
                  validator=validate_market_trading_pair_tuple,
                  prompt_on_new=True),
    "trade_side":
        ConfigVar(key="trade_side",
                  prompt="What operation will be executed? (buy/sell) >>> ",
                  type_str="str",
                  validator=lambda v: None if v in {"buy", "sell", ""} else "Invalid operation type.",
                  default="buy",
                  prompt_on_new=True),
    "target_asset_amount":
        ConfigVar(key="target_asset_amount",
                  prompt=target_asset_amount_prompt,
                  default=1.0,
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, min_value=Decimal("0"), inclusive=False),
                  prompt_on_new=True),
    "order_step_size":
        ConfigVar(key="order_step_size",
                  prompt="What is the amount of each individual order (denominated in the base asset, default is 1)? "
                         ">>> ",
                  default=1.0,
                  type_str="decimal",
                  validator=validate_order_step_size,
                  prompt_on_new=True),
    "order_price":
        ConfigVar(key="order_price",
                  prompt="What is the price for the limit orders? >>> ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, min_value=Decimal("0"), inclusive=False),
                  prompt_on_new=True),
    "is_delayed_start_execution":
        ConfigVar(key="is_delayed_start_execution",
                  prompt="Do you want to specify a start time for the execution? (Yes/No) >>> ",
                  type_str="bool",
                  default=False,
                  validator=validate_bool,
                  prompt_on_new=True),
    "start_datetime":
        ConfigVar(key="start_datetime",
                  prompt="Please enter the start date and time"
                         " (YYYY-MM-DD HH:MM:SS) >>> ",
                  type_str="str",
                  validator=validate_datetime_iso_string,
                  required_if=lambda: twap_config_map.get("is_time_span_execution").value or twap_config_map.get("is_delayed_start_execution").value,
                  prompt_on_new=True),
    "is_time_span_execution":
        ConfigVar(key="is_time_span_execution",
                  prompt="Do you want to specify an end time for the execution? (Yes/No) >>> ",
                  type_str="bool",
                  default=False,
                  validator=validate_bool,
                  prompt_on_new=True),
    "end_datetime":
        ConfigVar(key="end_datetime",
                  prompt="Please enter the end date and time"
                         " (YYYY-MM-DD HH:MM:SS) >>> ",
                  type_str="str",
                  validator=validate_datetime_iso_string,
                  on_validated=set_order_delay_default,
                  required_if=lambda: twap_config_map.get("is_time_span_execution").value,
                  prompt_on_new=True),
    "order_delay_time":
        ConfigVar(key="order_delay_time",
                  prompt="How many seconds do you want to wait between each individual order?"
                         " (Enter 10 to indicate 10 seconds)? >>> ",
                  type_str="float",
                  default=10,
                  validator=lambda v: validate_decimal(v, 0, inclusive=False),
                  required_if=lambda: twap_config_map.get("is_time_span_execution").value or twap_config_map.get("is_delayed_start_execution").value,
                  prompt_on_new=True),
    "cancel_order_wait_time":
        ConfigVar(key="cancel_order_wait_time",
                  prompt="How long do you want to wait before cancelling your limit order (in seconds). "
                         "(Default is 60 seconds) ? >>> ",
                  type_str="float",
                  default=60,
                  validator=lambda v: validate_decimal(v, 0, inclusive=False),
                  prompt_on_new=True)
}
