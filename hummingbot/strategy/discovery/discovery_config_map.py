from typing import (
    Any,
    Set,
)

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import is_exchange
from hummingbot.client.settings import EXAMPLE_PAIRS, required_exchanges
from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher


def discovery_trading_pair_list_prompt(market_name):
    return "Enter list of trading pairs or token names on %s (e.g. [%s] or press ENTER for all trading pairs) >>> " % (
        market_name,
        EXAMPLE_PAIRS.get(market_name, ""),
    )


def is_token(input_str: str):
    return input_str.startswith("<") and input_str.endswith(">")


def valid_token_or_trading_pair_array(market: str, input_list: Any):
    try:
        if isinstance(input_list, str):
            if len(input_list) == 0:
                return True
            filtered: filter = filter(lambda x: x not in ['[', ']', '"', "'"], list(input_list))
            input_list = "".join(filtered).split(",")
            input_list = [s.strip() for s in input_list]  # remove leading and trailing whitespaces

        single_token_inputs = list(filter(is_token, input_list))
        trading_pair_inputs = list(filter(lambda x: not is_token(x), input_list))

        known_trading_pairs = TradingPairFetcher.get_instance().trading_pairs.get(market, [])
        if len(known_trading_pairs) == 0:
            return True
        else:
            from hummingbot.client.hummingbot_application import MARKET_CLASSES
            from hummingbot.client.hummingbot_application import HummingbotApplication

            market_class = MARKET_CLASSES[market]
            valid_token_set: Set[str] = set()
            known_trading_pairs = HummingbotApplication._convert_to_exchange_trading_pair(market, known_trading_pairs)
            for known_trading_pair in known_trading_pairs:
                try:
                    base, quote = market_class.split_trading_pair(known_trading_pair)
                    valid_token_set.update([base, quote])
                except Exception:
                    # Add this catch to prevent trading_pairs with bad format to break the validator
                    continue
            return all([token[1:-1] in valid_token_set for token in single_token_inputs]) and \
                all([trading_pair in known_trading_pairs for trading_pair in trading_pair_inputs])
    except Exception:
        return False


discovery_config_map = {
    "primary_market": ConfigVar(
        key="primary_market",
        prompt="Enter your first exchange name >>> ",
        validator=is_exchange,
        on_validated=lambda value: required_exchanges.append(value),
    ),
    "secondary_market": ConfigVar(
        key="secondary_market",
        prompt="Enter your second exchange name >>> ",
        validator=is_exchange,
        on_validated=lambda value: required_exchanges.append(value),
    ),
    "target_trading_pair_1": ConfigVar(
        key="target_trading_pair_1",
        prompt=lambda: discovery_trading_pair_list_prompt(discovery_config_map.get("primary_market").value),
        validator=lambda value: valid_token_or_trading_pair_array(discovery_config_map.get("primary_market").value,
                                                                  value),
        type_str="list",
        default=[],
    ),
    "target_trading_pair_2": ConfigVar(
        key="target_trading_pair_2",
        prompt=lambda: discovery_trading_pair_list_prompt(discovery_config_map.get("secondary_market").value),
        validator=lambda value: valid_token_or_trading_pair_array(discovery_config_map.get("secondary_market").value,
                                                                  value),
        type_str="list",
        default=[],
    ),
    "equivalent_tokens": ConfigVar(
        key="equivalent_tokens",
        prompt=None,
        type_str="list",
        required_if=lambda: False,
        default=[["USDT", "USDC", "USDS", "DAI", "PAX", "TUSD", "USD"], ["ETH", "WETH"], ["BTC", "WBTC"]],
    ),
    "target_profitability": ConfigVar(
        key="target_profitability",
        prompt="What is the target profitability for discovery? (Default to "
        "0.0 to list maximum profitable amounts) >>> ",
        default=0.0,
        type_str="float",
    ),
    "target_amount": ConfigVar(
        key="target_amount",
        prompt="What is the max order size for discovery? " "(Default to infinity) >>> ",
        default=float("inf"),
        type_str="float",
    ),
}
