from os.path import (
    realpath,
    join,
)
from typing import List

from hummingbot import get_strategy_list
from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher

# Global variables
required_exchanges: List[str] = []
trading_pair_fetcher = TradingPairFetcher.get_instance()

# Global static values
KEYFILE_PREFIX = "key_file_"
KEYFILE_POSTFIX = ".json"
GLOBAL_CONFIG_PATH = "conf/conf_global.yml"
TOKEN_ADDRESSES_FILE_PATH = realpath(join(__file__, "../../wallet/ethereum/erc20_tokens.json"))
DEFAULT_KEY_FILE_PATH = "conf/"
DEFAULT_LOG_FILE_PATH = "logs/"
DEFAULT_ETHEREUM_RPC_URL = "https://mainnet.coinalpha.com/hummingbot-test-node"
TEMPLATE_PATH = realpath(join(__file__, "../../templates/"))
CONF_FILE_PATH = "conf/"
CONF_PREFIX = "conf_"
CONF_POSTFIX = "_strategy"

EXCHANGES = {
    "bamboo_relay",
    "binance",
    "coinbase_pro",
    "ddex",
    "huobi",
    "idex",
    "radar_relay",
    "bittrex"
}

DEXES = {
    "bamboo_relay",
    "ddex",
    "idex",
    "radar_relay",
}

STRATEGIES: List[str] = get_strategy_list()

EXAMPLE_PAIRS = {
    "binance": "ZRXETH",
    "ddex": "ZRX-WETH",
    "idex": "ETH_ZRX",
    "radar_relay": "ZRX-WETH",
    "bamboo_relay": "ZRX-WETH",
    "coinbase_pro": "ETH-USDC",
    "huobi": "ethusdt"
}

EXAMPLE_ASSETS = {
    "binance": "ZRX",
    "ddex": "ZRX",
    "idex": "ETH=",
    "radar_relay": "ZRX",
    "bamboo_relay": "ZRX",
    "coinbase_pro": "ETH",
    "huobi": "eth"
}

MAXIMUM_OUTPUT_PANE_LINE_COUNT = 1000
MAXIMUM_LOG_PANE_LINE_COUNT = 1000
MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT = 100

# Liquidity Bounties:
LIQUIDITY_BOUNTY_CONFIG_PATH = "conf/conf_liquidity_bounty.yml"


# Values that were once a part of configuration but no longer needed.
# Keep them for reference in case a user is using outdated config files
DEPRECATED_CONFIG_VALUES = {
    "stop_loss_pct",
    "stop_loss_price_type",
    "stop_loss_base_token",
    "trade_size_override",
}
