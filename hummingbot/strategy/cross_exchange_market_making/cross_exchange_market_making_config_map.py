from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import is_exchange, is_valid_market_symbol
from hummingbot.client.settings import required_exchanges, EXAMPLE_PAIRS


def maker_symbol_prompt():
    maker_market = cross_exchange_market_making_config_map.get("maker_market").value
    example = EXAMPLE_PAIRS.get(maker_market)
    return "Enter the token symbol you would like to trade on %s%s >>> " % (
        maker_market,
        f" (e.g. {example})" if example else "",
    )


def taker_symbol_prompt():
    taker_market = cross_exchange_market_making_config_map.get("taker_market").value
    example = EXAMPLE_PAIRS.get(taker_market)
    return "Enter the token symbol you would like to trade on %s%s >>> " % (
        taker_market,
        f" (e.g. {example})" if example else "",
    )


# strategy specific validators
def is_valid_maker_market_symbol(value: str) -> bool:
    maker_market = cross_exchange_market_making_config_map.get("maker_market").value
    return is_valid_market_symbol(maker_market, value)


def is_valid_taker_market_symbol(value: str) -> bool:
    taker_market = cross_exchange_market_making_config_map.get("taker_market").value
    return is_valid_market_symbol(taker_market, value)


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
    "maker_market_symbol": ConfigVar(
        key="maker_market_symbol", prompt=maker_symbol_prompt, validator=is_valid_maker_market_symbol
    ),
    "taker_market_symbol": ConfigVar(
        key="taker_market_symbol", prompt=taker_symbol_prompt, validator=is_valid_taker_market_symbol
    ),
    "min_profitability": ConfigVar(
        key="min_profitability",
        prompt="What is the minimum profitability for you to make a trade? " "(Enter 0.01 to indicate 1%) >>> ",
        type_str="float",
    ),
    "order_amount": ConfigVar(
        key="order_amount",
        prompt="What is your preferred trade size? (denominated in " "the base asset) >>> ",
        required_if=lambda: False,
        default=0.0,
        type_str="float",
    )
}
