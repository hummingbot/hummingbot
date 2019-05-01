from hummingbot.cli.config.config_var import ConfigVar
from hummingbot.cli.config.config_validators import is_exchange
from hummingbot.cli.settings import (
    required_exchanges,
    EXAMPLE_PAIRS,
)


def maker_symbol_prompt():
    maker_market = cross_exchange_market_making_config_map.get("maker_market").value
    example = EXAMPLE_PAIRS.get(maker_market)
    return "Enter the token symbol you would like to trade on %s%s >>> " \
           % (maker_market, f" (e.g. {example})" if example else "")


def taker_symbol_prompt():
    taker_market = cross_exchange_market_making_config_map.get("taker_market").value
    example = EXAMPLE_PAIRS.get(taker_market)
    return "Enter the token symbol you would like to trade on %s%s >>> " \
           % (taker_market, f" (e.g. {example})" if example else "")


cross_exchange_market_making_config_map = {
    "maker_market":                     ConfigVar(key="maker_market",
                                                  prompt="Enter your maker exchange name >>> ",
                                                  validator=is_exchange,
                                                  on_validated=lambda value: required_exchanges.append(value)),
    "taker_market":                     ConfigVar(key="taker_market",
                                                  prompt="Enter your taker exchange name >>> ",
                                                  validator=is_exchange,
                                                  on_validated=lambda value: required_exchanges.append(value)),
    "maker_market_symbol":              ConfigVar(key="maker_market_symbol",
                                                  prompt=maker_symbol_prompt),
    "taker_market_symbol":              ConfigVar(key="taker_market_symbol",
                                                  prompt=taker_symbol_prompt),
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
                                                         "e order book to make a trade? >>> ",
                                                  type_str="list",
                                                  required_if=lambda: False,
                                                  default=[
                                                      ["^.+(USDT|USDC|USDS|DAI|PAX|TUSD)$", 1000],
                                                      ["^.+ETH$", 10],
                                                      ["^.+BTC$", 0.5],
                                                  ]),
    "active_order_canceling":           ConfigVar(key="active_order_canceling",
                                                  prompt="Do you want to actively adjust/cancel orders? (Default "\
                                                         "True, only set to False if maker market is Radar Relay) >>> ",
                                                  type_str="bool",
                                                  default=True),
    # Setting the default threshold to -1.0 when to active_order_canceling is disabled
    # prevent canceling orders after it has expired
    "cancel_order_threshold":           ConfigVar(key="cancel_order_threshold",
                                                  prompt="What is the minimum profitability to actively cancel orders? "
                                                         "(Default to -1.0, only specify when active_order_canceling "
                                                         "is disabled, value can be negative) >>> ",
                                                  default=-1.0,
                                                  type_str="float"),
    "limit_order_min_expiration":       ConfigVar(key="limit_order_min_expiration",
                                                  prompt="What is the minimum limit order expiration in seconds? "
                                                         "(Default to 130 seconds) >>> ",
                                                  default=130.0,
                                                  type_str="float")
}