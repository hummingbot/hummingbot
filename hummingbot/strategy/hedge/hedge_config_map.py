from decimal import Decimal
from typing import Optional

from hummingbot.client.config.config_validators import (
    validate_bool,
    validate_connector,
    validate_decimal,
    validate_int,
    validate_market_trading_pair,
)
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import required_exchanges

MAX_CONNECTOR = 5


def validate_exchange_trading_pair(value: str) -> Optional[str]:
    exchange = hedge_config_map.get("hedge_connector").value
    return validate_market_trading_pair(exchange, value)


def validate_position_mode(value: str) -> Optional[str]:
    if value.lower() not in ["oneway", "hedge"]:
        return "Position mode must be either ONEWAY or HEDGE"
    return None


def market_validate(exchange: str, value: str) -> Optional[str]:
    markets = value.split(",")
    for market in markets:
        validated = validate_market_trading_pair(exchange, market)
        if validated:
            return validated
    return None


def validate_offsets(markets: str, value: str) -> Optional[str]:
    """checks and ensure offsets are of decimal type"""
    offsets = value.split(",")
    markets = markets.split(",")
    for offset in offsets:
        if validate_decimal(offset):
            return validate_decimal(offset)
    return None


hedge_config_map = {
    "strategy": ConfigVar(key="strategy", prompt="", default="hedge"),
    "hedge_connector": ConfigVar(
        key="hedge_connector",
        prompt="Enter the exchange to use to hedge overall asset >>> ",
        validator=validate_connector,
        on_validated=lambda value: required_exchanges.add(value),
        prompt_on_new=True,
    ),
    "hedge_markets": ConfigVar(
        key="hedge_markets",
        prompt="Enter the markets to hedge amount to hedge comma seperated. "
        "If value_mode is True, then only enter one market to for the strategy to hedge on. "
        "If not, list the markets that you want to hedge. "
        "Only markets with the same base as the hedge market will be hedged. >>>",
        type_str="str",
        validator=lambda x: market_validate(hedge_config_map["hedge_connector"], x),
        prompt_on_new=True,
    ),
    "hedge_offsets": ConfigVar(
        key="hedge_offsets",
        prompt="Enter the offsets to use to hedge the markets comma seperated. "
        "the remainder will be assumed as 0 if no inputs. "
        "e.g if markets is BTC-USDT,ETH-USDT,LTC-USDT. "
        "and offsets is 0.1, -0.2. "
        "then the offset amount that will be added is 0.1 BTC, -0.2 ETH and 0 LTC. ",
        type_str="str",
        validator=lambda x: validate_offsets(hedge_config_map["hedge_markets"].value, x),
        prompt_on_new=True,
        default="0",
    ),
    "hedge_leverage": ConfigVar(
        key="hedge_leverage",
        prompt="How much leverage do you want to use? applicable for derivatives only >>> ",
        type_str="int",
        default=int(1),
        validator=lambda v: validate_int(v, min_value=1, inclusive=True),
        prompt_on_new=False,
    ),
    "hedge_interval": ConfigVar(
        key="hedge_interval",
        prompt="how often do you want to check the hedge >>> ",
        type_str="decimal",
        default=Decimal(10),
        validator=lambda v: validate_decimal(v, min_value=0, inclusive=False),
        prompt_on_new=False,
    ),
    "hedge_ratio": ConfigVar(
        key="hedge_ratio",
        prompt="Enter ratio of asset to hedge, e.g 0.5 means 50 percent of the total asset value will be hedged. >>> ",
        default=Decimal("1"),
        type_str="decimal",
        validator=validate_decimal,
        prompt_on_new=False,
    ),
    "hedge_position_mode": ConfigVar(
        key="hedge_position_mode",
        prompt="What is the position mode to execute the trade on (ONEWAY/HEDGE)? >>> ",
        type_str="str",
        default="ONEWAY",
        validator=validate_position_mode,
        prompt_on_new=False,
    ),
    "min_trade_size": ConfigVar(
        key="min_trade_size",
        prompt="Enter minimum trade size in quote asset >>> ",
        type_str="decimal",
        validator=lambda v: validate_decimal(v, 0, inclusive=True),
        prompt_on_new=True,
    ),
    "slippage": ConfigVar(
        key="slippage",
        prompt="Enter max slippage in decimal, e.g 0.1 -> 10% >>> ",
        default=Decimal("0.01"),
        type_str="decimal",
        validator=lambda v: validate_decimal(v, 0, inclusive=True),
        prompt_on_new=False,
    ),
    "value_mode": ConfigVar(
        key="value_mode",
        prompt="Do you want to hedge by asset value [y] or asset amount[n] (y/n) >>> ",
        type_str="bool",
        validator=validate_bool,
        prompt_on_new=True,
    ),
}

for i in range(MAX_CONNECTOR):
    hedge_config_map[f"enable_connector_{i}"] = ConfigVar(
        key=f"enable_connector_{i}",
        prompt=f"Enable exchange {i} (y/n) >>> ",
        type_str="bool",
        validator=validate_bool,
        prompt_on_new=True,
    )
    hedge_config_map[f"connector_{i}"] = ConfigVar(
        key=f"connector_{i}",
        prompt="Enter the exchange to be hedged >>> ",
        validator=validate_connector,
        on_validated=lambda value: required_exchanges.add(value),
        required_if=lambda i=i: hedge_config_map.get(f"enable_connector_{i}").value is True,
        prompt_on_new=True,
    )
    hedge_config_map[f"markets_{i}"] = ConfigVar(
        key=f"markets_{i}",
        prompt="Enter the markets to check amount to hedge comma seperated. "
        "Use the market with the quote asset same as the hedge market. "
        "If value mode is True, This will be used to calculate the total value in the quote asset to be hedged. "
        "e.g if hedge_market is BTC-USDT, the taker market can be BTC-USDT,ETH-USDT. "
        "If value mode is False, this will be used to calculate the amount to hedge. "
        "e.g if hedge_market is BTC-USDT, the taker market can only be BTC-USDT. "
        "if the market does not exist in hedge_markets, it will not be hedged >>> ",
        type_str="str",
        validator=lambda x, i=i: market_validate(hedge_config_map[f"connector_{i}"], x),
        required_if=lambda i=i: hedge_config_map.get(f"enable_connector_{i}").value is True,
        prompt_on_new=True,
    )
    hedge_config_map[f"offsets_{i}"] = ConfigVar(
        key=f"offsets_{i}",
        prompt="Enter the offsets to add to each asset current amount before calculation, comma seperated. "
        "the length of the list should be the same as the length of the markets list. "
        "e.g if markets is BTC-USDT,ETH-USDT,LTC-USDT. "
        "and offsets is 0.1, -0.2. "
        "then the offset amount that will be added is 0.1 BTC, -0.2 ETH and -0.2 LTC. >>> ",
        type_str="str",
        validator=lambda x, i=i: validate_offsets(hedge_config_map[f"markets_{i}"].value, x),
        required_if=lambda i=i: hedge_config_map.get(f"enable_connector_{i}").value is True,
        prompt_on_new=True,
    )
