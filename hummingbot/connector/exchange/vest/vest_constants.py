import sys

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import OrderState

CLIENT_ID_PREFIX = "hummingbot"
MAX_ID_LEN = 32
SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 30 * 0.8

# Environment configuration
VEST_ENVIRONMENTS = {
    "prod": {
        "rest_url": "https://server-prod.hz.vestmarkets.com",
        "ws_url": "wss://ws-prod.hz.vestmarkets.com/ws-api?version=1.0"
    },
    "dev": {
        "rest_url": "https://server-dev.hz.vestmarkets.com",
        "ws_url": "wss://ws-dev.hz.vestmarkets.com/ws-api?version=1.0"
    }
}

DEFAULT_ENVIRONMENT = "prod"
DEFAULT_DOMAIN = VEST_ENVIRONMENTS[DEFAULT_ENVIRONMENT]["rest_url"]


def get_vest_base_url(environment: str = DEFAULT_ENVIRONMENT) -> str:
    """Returns Vest REST base URL based on environment"""
    return VEST_ENVIRONMENTS[environment]["rest_url"]


def get_vest_ws_url(environment: str = DEFAULT_ENVIRONMENT) -> str:
    """Returns Vest WebSocket URL based on environment"""
    return VEST_ENVIRONMENTS[environment]["ws_url"]


# REST API endpoints
VEST_BASE_PATH = "/v2"
VEST_EXCHANGE_INFO_PATH = f"{VEST_BASE_PATH}/exchangeInfo"
VEST_ACCOUNT_PATH = f"{VEST_BASE_PATH}/account"
VEST_ORDERS_PATH = f"{VEST_BASE_PATH}/orders"
VEST_WITHDRAW_PATH = f"{VEST_BASE_PATH}/transfer/withdraw"
VEST_TICKER_PATH = f"{VEST_BASE_PATH}/ticker/latest"
VEST_TRADES_PATH = f"{VEST_BASE_PATH}/trades"
VEST_ORDERBOOK_PATH = f"{VEST_BASE_PATH}/orderbook"

# WebSocket channels
VEST_WS_ACCOUNT_CHANNEL = "account_private"
VEST_WS_TICKERS_CHANNEL = "tickers"
VEST_WS_TRADES_CHANNEL = "trades"
VEST_WS_DEPTH_CHANNEL = "depth"
VEST_WS_KLINE_CHANNEL = "kline"

VEST_WS_CHANNELS = {
    VEST_WS_ACCOUNT_CHANNEL,
}

# Rate limiting (conservative estimates since not specified in docs)
WS_CONNECTION_LIMIT_ID = "WSConnection"
WS_REQUEST_LIMIT_ID = "WSRequest"
WS_SUBSCRIPTION_LIMIT_ID = "WSSubscription"

ORDER_STATE = {
    "NEW": OrderState.OPEN,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "FILLED": OrderState.FILLED,
    "CANCELLED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
}

ORDER_TYPE_MAP = {
    OrderType.LIMIT: "LIMIT",
    OrderType.MARKET: "MARKET",
    OrderType.LIMIT_MAKER: "LIMIT_MAKER",
}

SIDE_MAP = {
    "BUY": "Buy",
    "SELL": "Sell",
}

NO_LIMIT = sys.maxsize

# Conservative rate limits (not specified in API docs)
RATE_LIMITS = [
    RateLimit(WS_CONNECTION_LIMIT_ID, limit=5, time_interval=1),
    RateLimit(WS_REQUEST_LIMIT_ID, limit=100, time_interval=60),
    RateLimit(WS_SUBSCRIPTION_LIMIT_ID, limit=240, time_interval=60 * 60),
    RateLimit(limit_id=VEST_EXCHANGE_INFO_PATH, limit=10, time_interval=60),
    RateLimit(limit_id=VEST_ACCOUNT_PATH, limit=10, time_interval=1),
    RateLimit(limit_id=VEST_ORDERS_PATH, limit=20, time_interval=1),
    RateLimit(limit_id=VEST_WITHDRAW_PATH, limit=5, time_interval=60),
    RateLimit(limit_id=VEST_TICKER_PATH, limit=10, time_interval=1),
    RateLimit(limit_id=VEST_TRADES_PATH, limit=10, time_interval=1),
    RateLimit(limit_id=VEST_ORDERBOOK_PATH, limit=10, time_interval=1),
]
