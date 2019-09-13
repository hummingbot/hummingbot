from os.path import (
    realpath,
    join,
)
from typing import List

from hummingbot.core.utils.symbol_fetcher import SymbolFetcher

# Global variables
required_exchanges: List[str] = []
symbol_fetcher = SymbolFetcher.get_instance()

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
}

DEXES = {
    "bamboo_relay",
    "ddex",
    "idex",
    "radar_relay",
}

STRATEGIES = {
    "cross_exchange_market_making",
    "arbitrage",
    "discovery",
    "pure_market_making",
    "simple_trade"
}

EXAMPLE_PAIRS = {
    "binance": "ZRXETH",
    "ddex": "ZRX-WETH",
    "idex": "ETH_ZRX",
    "radar_relay": "ZRX-WETH",
    "bamboo_relay": "ZRX-WETH",
    "coinbase_pro": "ETH-USDC",
    "huobi": "ethusdt"
}

MAXIMUM_OUTPUT_PANE_LINE_COUNT = 1000
MAXIMUM_LOG_PANE_LINE_COUNT = 1000
MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT = 100

# Liquidity Bounties:
LIQUIDITY_BOUNTY_CONFIG_PATH = "conf/conf_liquidity_bounty.yml"
MIN_ETH_STAKED_REQUIREMENT = 0.05


# Values that were once a part of configuration but no longer needed.
# Keep them for reference in case a user is using outdated config files
DEPRECATED_CONFIG_VALUES = {
    "stop_loss_pct",
    "stop_loss_price_type",
    "stop_loss_base_token",
}