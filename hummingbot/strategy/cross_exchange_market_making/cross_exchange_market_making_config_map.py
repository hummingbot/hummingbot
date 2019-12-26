from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    is_exchange,
    is_valid_market_trading_pair
)
from hummingbot.client.settings import required_exchanges, EXAMPLE_PAIRS


def maker_trading_pair_prompt():
    maker_market = cross_exchange_market_making_config_map.get("maker_market").value
    example = EXAMPLE_PAIRS.get(maker_market)
    return "Enter the token trading pair you would like to trade on maker market: %s%s >>> " % (
        maker_market,
        f" (e.g. {example})" if example else "",
    )


def taker_trading_pair_prompt():
    taker_market = cross_exchange_market_making_config_map.get("taker_market").value
    example = EXAMPLE_PAIRS.get(taker_market)
    return "Enter the token trading pair you would like to trade on taker market: %s%s >>> " % (
        taker_market,
        f" (e.g. {example})" if example else "",
    )


# strategy specific validators
def is_valid_maker_market_trading_pair(value: str) -> bool:
    maker_market = cross_exchange_market_making_config_map.get("maker_market").value
    return is_valid_market_trading_pair(maker_market, value)


def is_valid_taker_market_trading_pair(value: str) -> bool:
    taker_market = cross_exchange_market_making_config_map.get("taker_market").value
    return is_valid_market_trading_pair(taker_market, value)


cross_exchange_market_making_config_map = {
    "maker_market": ConfigVar(
        key="maker_market",
        prompt="Enter your maker exchange name >>> ",
        validator=is_exchange,
        on_validated=lambda value: required_exchanges.append(value),
    ),
    "taker_market": ConfigVar(
        key="taker_market",
        prompt="Enter your taker exchange name >>> ",
        validator=is_exchange,
        on_validated=lambda value: required_exchanges.append(value),
    ),
    "maker_market_trading_pair": ConfigVar(
        key="maker_market_trading_pair",
        prompt=maker_trading_pair_prompt,
        validator=is_valid_maker_market_trading_pair
    ),
    "taker_market_trading_pair": ConfigVar(
        key="taker_market_trading_pair",
        prompt=taker_trading_pair_prompt,
        validator=is_valid_taker_market_trading_pair
    ),
    "min_profitability": ConfigVar(
        key="min_profitability",
        prompt="What is the minimum profitability for you to make a trade? (Enter 0.01 to indicate 1%) >>> ",
        type_str="decimal",
    ),
    "order_amount": ConfigVar(
        key="order_amount",
        prompt="What is your preferred trade size? (Denominated in the base asset) >>> ",
        default=0.0,
        type_str="decimal",
    ),
    "adjust_order_enabled": ConfigVar(
        key="adjust_order_enabled",
        prompt="",
        default=True,
        type_str="bool",
        required_if=lambda: False,
    ),
    "active_order_canceling": ConfigVar(
        key="active_order_canceling",
        prompt="",
        type_str="bool",
        default=True,
        required_if=lambda: False,
    ),
    # Setting the default threshold to 0.05 when to active_order_canceling is disabled
    # prevent canceling orders after it has expired
    "cancel_order_threshold": ConfigVar(
        key="cancel_order_threshold",
        prompt="",
        default=0.05,
        type_str="decimal",
        required_if=lambda: False,
    ),
    "limit_order_min_expiration": ConfigVar(
        key="limit_order_min_expiration",
        prompt="",
        default=130.0,
        type_str="float",
        required_if=lambda: False,
    ),
    "top_depth_tolerance": ConfigVar(
        key="top_depth_tolerance",
        prompt="",
        default=0,
        type_str="decimal",
        required_if=lambda: False,
    ),
    "anti_hysteresis_duration": ConfigVar(
        key="anti_hysteresis_duration",
        prompt="",
        default=60,
        type_str="float",
        required_if=lambda: False,
    ),
    "order_size_taker_volume_factor": ConfigVar(
        key="order_size_taker_volume_factor",
        prompt="",
        default=0.25,
        type_str="decimal",
        required_if=lambda: False,
    ),
    "order_size_taker_balance_factor": ConfigVar(
        key="order_size_taker_balance_factor",
        prompt="",
        default=0.995,
        type_str="decimal",
        required_if=lambda: False,
    ),
    "order_size_portfolio_ratio_limit": ConfigVar(
        key="order_size_portfolio_ratio_limit",
        prompt="",
        default=0.1667,
        type_str="decimal",
        required_if=lambda: False,
    )
}
