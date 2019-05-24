from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    is_exchange,
    is_valid_market_symbol,
)
from hummingbot.client.settings import (
    required_exchanges,
    EXAMPLE_PAIRS,
)


def is_valid_primary_market_symbol(value: str) -> bool:
    primary_market = arbitrage_config_map.get("primary_market").value
    return is_valid_market_symbol(primary_market, value)


def is_valid_secondary_market_symbol(value: str) -> bool:
    secondary_market = arbitrage_config_map.get("secondary_market").value
    return is_valid_market_symbol(secondary_market, value)


def primary_symbol_prompt():
    primary_market = arbitrage_config_map.get("primary_market").value
    example = EXAMPLE_PAIRS.get(primary_market)
    return "Enter the token symbol you would like to trade on %s%s >>> " \
           % (primary_market, f" (e.g. {example})" if example else "")


def secondary_symbol_prompt():
    secondary_market = arbitrage_config_map.get("secondary_market").value
    example = EXAMPLE_PAIRS.get(secondary_market)
    return "Enter the token symbol you would like to trade on %s%s >>> " \
           % (secondary_market, f" (e.g. {example})" if example else "")


arbitrage_config_map = {
    "primary_market":                   ConfigVar(key="primary_market",
                                                  prompt="Enter your primary exchange name >>> ",
                                                  validator=is_exchange,
                                                  on_validated=lambda value: required_exchanges.append(value)),
    "secondary_market":                 ConfigVar(key="secondary_market",
                                                  prompt="Enter your secondary exchange name >>> ",
                                                  validator=is_exchange,
                                                  on_validated=lambda value: required_exchanges.append(value)),
    "primary_market_symbol":            ConfigVar(key="primary_market_symbol",
                                                  prompt=primary_symbol_prompt),
    "secondary_market_symbol":          ConfigVar(key="secondary_market_symbol",
                                                  prompt=secondary_symbol_prompt),
    "min_profitability":                ConfigVar(key="min_profitability",
                                                  prompt="What is the minimum profitability for you to make a trade? "\
                                                         "(Enter 0.01 to indicate 1%) >>> ",
                                                  default=0.003,
                                                  type_str="float"),
    "trade_size_override":              ConfigVar(key="trade_size_override",
                                                  prompt="What is your preferred trade size? (denominated in "
                                                         "the quote asset) >>> ",
                                                  required_if=lambda: False,
                                                  default=0.0,
                                                  type_str="float"),
    "top_depth_tolerance":              ConfigVar(key="top_depth_tolerance",
                                                  prompt="What is the maximum depth you would go into th"
                                                         "e order book to make a trade? >>>",
                                                  type_str="list",
                                                  required_if=lambda: False,
                                                  default=[
                                                      ["^.+(USDT|USDC|USDS|DAI|PAX|TUSD)$", 1000],
                                                      ["^.+ETH$", 10],
                                                      ["^.+BTC$", 0.5],
                                                  ]),
}
