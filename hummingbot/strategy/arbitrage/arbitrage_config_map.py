from hummingbot.cli.config.config_var import ConfigVar
from hummingbot.cli.config.validators import is_exchange
from hummingbot.cli.settings import (
    required_exchanges,
    EXAMPLE_PAIRS,
)


def primary_symbol_prompt():
    primary_market = arbitrage_config_map.get("primary_market").value
    return "Enter the token symbol you would like to trade on %s (e.g. %s) >>> " \
           % (primary_market, EXAMPLE_PAIRS[primary_market])


def secondary_symbol_prompt():
    secondary_market = arbitrage_config_map.get("secondary_market").value
    return "Enter the token symbol you would like to trade on %s (e.g. %s) >>> " \
           % (secondary_market, EXAMPLE_PAIRS[secondary_market])


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
