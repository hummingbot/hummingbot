from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    is_exchange,
)
from hummingbot.client.settings import (
    EXAMPLE_PAIRS,
    required_exchanges,
)
from hummingbot.core.utils.symbol_fetcher import SymbolFetcher
from typing import Any


def discovery_symbol_list_prompt(market_name):
    return "Enter list of token symbol on %s (e.g. ['%s'] or press ENTER for all symbols.) >>> " \
           % (market_name, EXAMPLE_PAIRS.get(market_name, ""))


def trading_pair_array_validator(market: str, trading_pair_list: Any):
    try:
        if type(trading_pair_list) is str:
            if len(trading_pair_list) == 0:
                return True
            trading_pair_list = eval(trading_pair_list)

        known_symbols = SymbolFetcher.get_instance().symbols.get(market, [])
        if len(known_symbols) == 0:
            return True
        else:
            return all([trading_pair in known_symbols for trading_pair in trading_pair_list])
    except Exception:
        return False


discovery_config_map = {
    "primary_market":                   ConfigVar(key="primary_market",
                                                  prompt="Enter your first exchange name >>> ",
                                                  validator=is_exchange,
                                                  on_validated=lambda value: required_exchanges.append(value)),
    "secondary_market":                 ConfigVar(key="secondary_market",
                                                  prompt="Enter your second exchange name >>> ",
                                                  validator=is_exchange,
                                                  on_validated=lambda value: required_exchanges.append(value)),

    "target_symbol_1":                  ConfigVar(key="target_symbol_1",
                                                  prompt=lambda: discovery_symbol_list_prompt(
                                                      discovery_config_map.get("primary_market").value
                                                  ),
                                                  validator=lambda value: trading_pair_array_validator(
                                                      discovery_config_map.get("primary_market").value, value,
                                                  ),
                                                  type_str="list",
                                                  default=[]),
    "target_symbol_2":                  ConfigVar(key="target_symbol_2",
                                                  prompt=lambda: discovery_symbol_list_prompt(
                                                      discovery_config_map.get("secondary_market").value
                                                  ),
                                                  validator=lambda value: trading_pair_array_validator(
                                                      discovery_config_map.get("secondary_market").value, value,
                                                  ),
                                                  type_str="list",
                                                  default=[]),
    "equivalent_tokens":                ConfigVar(key="equivalent_tokens",
                                                  prompt=None,
                                                  type_str="list",
                                                  required_if=lambda: False,
                                                  default=[
                                                      ["USDT", "USDC", "USDS", "DAI", "PAX", "TUSD", "USD"],
                                                      ["ETH", "WETH"],
                                                      ["BTC", "WBTC"]
                                                  ]),
    "target_profitability":             ConfigVar(key="target_profitability",
                                                  prompt="What is the target profitability for discovery? (default to "
                                                         "0.0 to list maximum profitable amounts) >>> ",
                                                  default=0.0,
                                                  type_str="float"),
    "target_amount":                    ConfigVar(key="target_amount",
                                                  prompt="What is the max order size for discovery? >>> "
                                                         "(default to infinity)",
                                                  default=float("inf"),
                                                  type_str="float"),
}