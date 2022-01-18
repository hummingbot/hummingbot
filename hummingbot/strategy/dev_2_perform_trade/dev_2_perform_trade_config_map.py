#!/usr/bin/env python
from decimal import Decimal
from typing import Optional

from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_market_trading_pair,
)
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import (
    required_exchanges,
    AllConnectorSettings,
)


def trading_pair_prompt():
    exchange = dev_2_perform_trade_config_map.get("exchange").value
    example = AllConnectorSettings.get_example_pairs().get(exchange)
    return "Enter the trading pair you would like to trade on %s%s >>> " \
           % (exchange, f" (e.g. {example})" if example else "")


# checks if the trading pair is valid
def validate_trading_pair(value: str) -> Optional[str]:
    exchange = dev_2_perform_trade_config_map.get("exchange").value
    return validate_market_trading_pair(exchange, value)


def validate_decimal(value: str, min_value: Decimal = None, max_value: Decimal = None, inclusive=True) -> Optional[str]:
    try:
        decimal_value = Decimal(value)
    except Exception:
        return f"{value} is not in decimal format."
    if inclusive:
        if min_value is not None and max_value is not None:
            if not (Decimal(str(min_value)) <= decimal_value <= Decimal(str(max_value))):
                return f"Value must be between {min_value} and {max_value}."
        elif min_value is not None and not decimal_value >= Decimal(str(min_value)):
            return f"Value cannot be less than {min_value}."
        elif max_value is not None and not decimal_value <= Decimal(str(max_value)):
            return f"Value cannot be more than {max_value}."
    else:
        if min_value is not None and max_value is not None:
            if not (Decimal(str(min_value)) < decimal_value < Decimal(str(max_value))):
                return f"Value must be between {min_value} and {max_value} (exclusive)."
        elif min_value is not None and not decimal_value > Decimal(str(min_value)):
            return f"Value must be more than {min_value}."
        elif max_value is not None and not decimal_value < Decimal(str(max_value)):
            return f"Value must be less than {max_value}."


def order_amount_prompt() -> str:
    trading_pair = dev_2_perform_trade_config_map["trading_pair"].value
    base_asset, quote_asset = trading_pair.split("-")
    return f"What is the amount of {base_asset} per order? >>> "


dev_2_perform_trade_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="dev_2_perform_trade"),
    "exchange":
        ConfigVar(key="exchange",
                  prompt="Enter the name of the exchange >>> ",
                  validator=validate_exchange,
                  on_validated=lambda value: required_exchanges.append(value),
                  prompt_on_new=True,
                  ),
    "trading_pair":
        ConfigVar(key="trading_pair",
                  prompt=trading_pair_prompt,
                  validator=validate_trading_pair,
                  prompt_on_new=True,
                  ),
    "is_buy":
        ConfigVar(key="is_buy",
                  prompt="Enter True for Buy order and False for Sell order (default is Buy Order) >>> ",
                  type_str="bool",
                  default=True,
                  prompt_on_new=True,
                  ),
    "spread":
        ConfigVar(key="spread",
                  prompt="How far away from the mid price do you want to place the "
                         "first bid order? (Enter 1 to indicate 1%) >>> ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, 100, inclusive=False),
                  prompt_on_new=True
                  ),
    "order_amount":
        ConfigVar(key="order_amount",
                  prompt=order_amount_prompt,
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, min_value=Decimal("0"), inclusive=False),
                  prompt_on_new=True,
                  ),
    "price_type":
        ConfigVar(key="price_type",
                  prompt="Which price type to use? ("
                         "mid_price/last_price/last_own_trade_price) >>> ",
                  type_str="str",
                  default="mid_price",
                  validator=lambda s: None
                  if s in {"mid_price", "last_price", "last_own_trade_price"}
                  else "Invalid price type.",
                  prompt_on_new=True,
                  ),
}
