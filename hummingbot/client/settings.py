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
ENCYPTED_CONF_PREFIX = "encrypted_"
ENCYPTED_CONF_POSTFIX = ".json"
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
    "liquid",
    "idex",
    "radar_relay",
    "dolomite",
    "bittrex",
    "bitcoin_com"
}

DEXES = {
    "bamboo_relay",
    "ddex",
    "idex",
    "radar_relay",
    "dolomite"
}

STRATEGIES: List[str] = get_strategy_list()

EXAMPLE_PAIRS = {
    "bamboo_relay": "ZRX-WETH",
    "binance": "ZRX-ETH",
    "bitcoin_com": "ETH-BCH",
    "bittrex": "ZRX-ETH",
    "coinbase_pro": "ETH-USDC",
    "ddex": "ZRX-WETH",
    "dolomite": "WETH-DAI",
    "huobi": "ETH-USDT",
    "idex": "ZRX-ETH",
    "liquid": "ETH-USD",
    "radar_relay": "ZRX-WETH",
}

EXAMPLE_ASSETS = {
    "bamboo_relay": "ZRX",
    "binance": "ZRX",
    "bitcoin_com": "BCH",
    "bittrex": "ZRX",
    "coinbase_pro": "ETH",
    "ddex": "ZRX",
    "dolomite": "LRC",
    "huobi": "eth",
    "idex": "ETH",
    "liquid": "ETH",
    "radar_relay": "ZRX",
}

MAXIMUM_OUTPUT_PANE_LINE_COUNT = 1000
MAXIMUM_LOG_PANE_LINE_COUNT = 1000
MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT = 100
