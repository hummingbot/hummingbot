import os

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import OrderState

# A single source of truth for constant variables related to the exchange

EXCHANGE_NAME = "rubin_perpetual"

API_VERSION = "v4"
CURRENCY = "USD"

HBOT_BROKER_ID = "Hummingbot"
MAX_ID_LEN = 40
HEARTBEAT_INTERVAL = 30.0
ORDER_EXPIRATION = 2419200  # 28 days

# height limited to 2147483647 for 32-bit OS, equivalent to 2038-01-19T03:14Z
TX_MAX_HEIGHT = 2147483647
LIMIT_FEE = 0.015

# API Base URLs
MAX_ID_BIT_COUNT = 31

# data_source grpc
RUBIN_AERIAL_GRPC_OR_REST_PREFIX = "grpc"

# ── Сеть: mainnet / testnet ───────────────────────────────────────────────
# Переключение сети: env RUBIN_PERPETUAL_DOMAIN = "mainnet" (по умолчанию) | "testnet".
# Также честно работает domain-параметр коннектора (getter'ы ниже принимают domain).
DOMAIN_ENDPOINTS = {
    "mainnet": {
        "grpc": "grpc.mainnet.rubin.trade:443",
        "validator_rest": "https://grpc.mainnet.rubin.trade:443",
        "indexer_rest": "https://indexer.mainnet.rubin.trade",
        "ws": "wss://indexer.mainnet.rubin.trade/{}/ws".format(API_VERSION),
        "chain_id": "ritbit-mainnet",
    },
    "testnet": {
        "grpc": "grpc.testnet.rubin.trade:443",
        "validator_rest": "https://grpc.testnet.rubin.trade:443",
        "indexer_rest": "https://indexer.testnet.rubin.trade",
        "ws": "wss://indexer.testnet.rubin.trade/{}/ws".format(API_VERSION),
        "chain_id": "ritbit-testnet",
    },
}
# Алиасы домена ("com" — легаси-значение = mainnet).
_DOMAIN_ALIASES = {"com": "mainnet", "main": "mainnet", "mainnet": "mainnet", "testnet": "testnet", "test": "testnet"}


def _resolve_domain(domain) -> str:
    return _DOMAIN_ALIASES.get(str(domain or "").strip().lower(), "mainnet")


# Сеть по умолчанию — из окружения (RUBIN_PERPETUAL_DOMAIN), иначе mainnet.
DEFAULT_DOMAIN = _resolve_domain(os.getenv("RUBIN_PERPETUAL_DOMAIN", "mainnet"))


def _ep(domain=None) -> dict:
    return DOMAIN_ENDPOINTS[_resolve_domain(domain) if domain else DEFAULT_DOMAIN]


def grpc_endpoint(domain=None) -> str:
    return _ep(domain)["grpc"]


def validator_rest_base(domain=None) -> str:
    return _ep(domain)["validator_rest"]


def indexer_rest_base(domain=None) -> str:
    return _ep(domain)["indexer_rest"]


def rest_url(domain=None) -> str:
    return "{}/{}".format(_ep(domain)["indexer_rest"], API_VERSION)


def ws_url(domain=None) -> str:
    return _ep(domain)["ws"]


def chain_id(domain=None) -> str:
    return _ep(domain)["chain_id"]


# Легаси-константы (для прямых ссылок CONSTANTS.*) — из сети по умолчанию.
RUBIN_AERIAL_CONFIG_URL = grpc_endpoint()
RUBIN_QUERY_AERIAL_CONFIG_URL = grpc_endpoint()
CHAIN_ID = chain_id()
RUBIN_VALIDATOR_REST_BASE_URL = validator_rest_base()
RUBIN_INDEXER_REST_BASE_URL = indexer_rest_base()
RUBIN_REST_URL = rest_url()
RUBIN_WS_URL = ws_url()

# Native chain-token denom: urit (micro-RIT). Одинаков на mainnet/testnet.
FEE_DENOMINATION = "urit"
TX_FEE = 0
TX_GAS_LIMIT = 0

# Public REST Endpoints

PATH_MARKETS = "/perpetualMarkets"

PATH_HISTORY_FUNDING = "/historicalFunding"
PATH_TICKER = "/stats"

PATH_SNAPSHOT = "/orderbooks/perpetualMarket"
PATH_TIME = "/time"

PATH_ORDERS = "/orders"

PATH_FILLS = "/fills"
PATH_POSITIONS = "/perpetualPositions"

PATH_ACCOUNTS = "/accounts"
PATH_CONFIG = "/config"

PATH_FUNDING = "/historical-pnl"

PATH_SUBACCOUNT = "/addresses"

# WS Endpoints
WS_PATH_ACCOUNTS = "/ws/accounts"

# WS Channels

WS_CHANNEL_TRADES = "v4_trades"
WS_CHANNEL_ORDERBOOK = "v4_orderbook"
WS_CHANNEL_MARKETS = "v4_markets"
WS_CHANNEL_ACCOUNTS = "v4_subaccounts"

WS_TYPE_SUBSCRIBE = "subscribe"
WS_TYPE_SUBSCRIBED = "subscribed"
WS_TYPE_CHANNEL_DATA = "channel_data"

TIF_GOOD_TIL_TIME = "GTT"
TIF_FILL_OR_KILL = "FOK"
TIF_IMMEDIATE_OR_CANCEL = "IOC"

FEES_KEY = "*"
FEE_MAKER_KEY = "maker"
FEE_TAKER_KEY = "taker"

ORDER_TYPE_MAP = {
    OrderType.LIMIT: "LIMIT",
    OrderType.LIMIT_MAKER: "LIMIT",
    OrderType.MARKET: "MARKET",
}

ORDER_STATE = {
    "PENDING": OrderState.OPEN,
    "OPEN": OrderState.OPEN,
    "BEST_EFFORT_OPENED": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "CANCELED": OrderState.CANCELED,
    "BEST_EFFORT_CANCELED": OrderState.PENDING_CANCEL,
}

WS_CHANNEL_TO_PATH = {WS_CHANNEL_ACCOUNTS: WS_PATH_ACCOUNTS}

LAST_FEE_PAYMENTS_MAX = 1
LAST_FILLS_MAX = 100

LIMIT_ID_GET = "LIMIT_ID_GET"
LIMIT_ID_ORDER_CANCEL = "LIMIT_ID_ORDER_CANCEL"
LIMIT_ID_LONG_TERM_ORDER_PLACE = "LIMIT_ID_LONG_TERM_ORDER_PLACE"

LIMIT_LONG_TERM_ORDER_PLACE = "LIMIT_LONG_TERM_ORDER_PLACE"
MARKET_SHORT_TERM_ORDER_PLACE = "LIMIT_LONG_TERM_ORDER_PLACE"

NO_LIMIT = 1000
ONE_SECOND = 1
ONE_HUNDRED_SECOND = 100

QUOTE_QUANTUMS_ATOMIC_RESOLUTION = -6
ORDER_FLAGS_SHORT_TERM = 0
ORDER_FLAGS_LONG_TERM = 64

TIME_IN_FORCE_IOC = 1
TIME_IN_FORCE_POST_ONLY = 2
TIME_IN_FORCE_UNSPECIFIED = 0

RATE_LIMITS = [
    # Pools
    RateLimit(limit_id=LIMIT_ID_GET, limit=NO_LIMIT, time_interval=ONE_SECOND),
    RateLimit(limit_id=LIMIT_LONG_TERM_ORDER_PLACE, limit=20, time_interval=ONE_HUNDRED_SECOND),
    RateLimit(limit_id=MARKET_SHORT_TERM_ORDER_PLACE, limit=200, time_interval=ONE_SECOND),
    # Weighted limits
    RateLimit(
        limit_id=PATH_CONFIG,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(LIMIT_ID_GET)],
    ),
    RateLimit(
        limit_id=PATH_FILLS,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(LIMIT_ID_GET)],
    ),
    RateLimit(
        limit_id=PATH_ORDERS,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(LIMIT_ID_GET)],
    ),
    RateLimit(
        limit_id=PATH_FUNDING,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(LIMIT_ID_GET)],
    ),
    RateLimit(
        limit_id=PATH_HISTORY_FUNDING,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(LIMIT_ID_GET)],
    ),
    RateLimit(
        limit_id=PATH_ACCOUNTS,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(LIMIT_ID_GET)],
    ),
    RateLimit(
        limit_id=PATH_SUBACCOUNT,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(LIMIT_ID_GET)],
    ),
    RateLimit(
        limit_id=PATH_MARKETS,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(LIMIT_ID_GET)],
    ),
    RateLimit(
        limit_id=PATH_TIME,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(LIMIT_ID_GET)],
    ),
    RateLimit(
        limit_id=PATH_SNAPSHOT,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(LIMIT_ID_GET)],
    ),
    RateLimit(
        limit_id=LIMIT_ID_LONG_TERM_ORDER_PLACE,
        limit=2,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(LIMIT_LONG_TERM_ORDER_PLACE)],
    ),
    RateLimit(
        limit_id=LIMIT_ID_ORDER_CANCEL,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,

    ),
]

ACCOUNT_SEQUENCE_MISMATCH_ERROR = "account sequence mismatch"
ERR_MSG_NO_ORDER_FOUND = "Stateful order does not exist"
