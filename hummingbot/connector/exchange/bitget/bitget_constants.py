from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "com"

HBOT_ORDER_ID_PREFIX = "HBOT"
MAX_ORDER_ID_LEN = 32

# Base URLs
REST_URL = "https://api.bitget.{}/api/spot/v1"
WSS_URL = "wss://ws.bitget.{}/spot/v1/stream"

# API Versions
PUBLIC_API_VERSION = "v1"
PRIVATE_API_VERSION = "v1"

# Public API endpoints
TICKER_PRICE_CHANGE_PATH_URL = "/market/ticker"
SNAPSHOT_PATH_URL = "/market/depth"
EXCHANGE_INFO_PATH_URL = "/public/products"
SERVER_TIME_PATH_URL = "/public/time"

# Private API endpoints
ACCOUNTS_PATH_URL = "/account/getInfo"
MY_TRADES_PATH_URL = "/trade/fills"
ORDER_PATH_URL = "/trade/order"

WS_HEARTBEAT_TIME_INTERVAL = 30

# Bitget parameters
SIDE_BUY = "buy"
SIDE_SELL = "sell"

TIME_IN_FORCE_GTC = "gtc"  # Good till canceled
TIME_IN_FORCE_IOC = "ioc"  # Immediate or cancel

# Rate Limit Types
IP_REQUEST_RATE_LIMIT = "IP_REQUEST_RATE_LIMIT"
UID_REQUEST_RATE_LIMIT = "UID_REQUEST_RATE_LIMIT"

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

# Rate Limits
RATE_LIMITS = [
    RateLimit(limit_id=IP_REQUEST_RATE_LIMIT, limit=60, time_interval=ONE_MINUTE),
    RateLimit(limit_id=UID_REQUEST_RATE_LIMIT, limit=30, time_interval=ONE_MINUTE),
    # Public endpoints
    RateLimit(
        limit_id=TICKER_PRICE_CHANGE_PATH_URL,
        limit=60,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(IP_REQUEST_RATE_LIMIT, 1)],
    ),
    RateLimit(
        limit_id=SNAPSHOT_PATH_URL,
        limit=60,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(IP_REQUEST_RATE_LIMIT, 1)],
    ),
    RateLimit(
        limit_id=EXCHANGE_INFO_PATH_URL,
        limit=60,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(IP_REQUEST_RATE_LIMIT, 1)],
    ),
    RateLimit(
        limit_id=SERVER_TIME_PATH_URL,
        limit=60,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(IP_REQUEST_RATE_LIMIT, 1)],
    ),
    # Private endpoints
    RateLimit(
        limit_id=ACCOUNTS_PATH_URL,
        limit=30,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(UID_REQUEST_RATE_LIMIT, 1)],
    ),
    RateLimit(
        limit_id=MY_TRADES_PATH_URL,
        limit=30,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(UID_REQUEST_RATE_LIMIT, 1)],
    ),
    RateLimit(
        limit_id=ORDER_PATH_URL,
        limit=30,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(UID_REQUEST_RATE_LIMIT, 1)],
    ),
]

# Error Codes and Messages
ORDER_NOT_EXIST_ERROR_CODE = "40009"
ORDER_NOT_EXIST_MESSAGE = "Order not found"
UNKNOWN_ORDER_ERROR_CODE = "40009"
UNKNOWN_ORDER_MESSAGE = "Unknown order"
TIMESTAMP_RELATED_ERROR_CODE = "40007"
TIMESTAMP_RELATED_ERROR_MESSAGE = "Timestamp expired"

# Order States
ORDER_STATE = {
    "new": OrderState.OPEN,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "filled": OrderState.FILLED,
    "canceled": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
    "expired": OrderState.FAILED,
}

# WebSocket Order States
WS_ORDER_STATE = {
    "1": OrderState.OPEN,
    "2": OrderState.PARTIALLY_FILLED,
    "3": OrderState.FILLED,
    "4": OrderState.CANCELED,
    "5": OrderState.OPEN,  # Pending cancel
    "6": OrderState.FAILED,  # Rejected
    "7": OrderState.FAILED,  # Expired
}

# WebSocket Event Types
DIFF_EVENT_TYPE = "depth"
TRADE_EVENT_TYPE = "trade"

USER_TRADES_ENDPOINT_NAME = "spot/fills"
USER_ORDERS_ENDPOINT_NAME = "spot/order"
USER_BALANCE_ENDPOINT_NAME = "spot/account"
WS_CONNECTION_TIME_INTERVAL = 20
RATE_LIMITS = [
    RateLimit(limit_id=IP_REQUEST_RATE_LIMIT, limit=1200, time_interval=ONE_MINUTE),
    RateLimit(limit_id=UID_REQUEST_RATE_LIMIT, limit=900, time_interval=ONE_MINUTE),
    # Weighted Limits
    RateLimit(
        limit_id=TICKER_PRICE_CHANGE_PATH_URL,
        limit=1200,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(IP_REQUEST_RATE_LIMIT, 1)]
    ),
    RateLimit(
        limit_id=SNAPSHOT_PATH_URL,
        limit=1200,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(IP_REQUEST_RATE_LIMIT, 1)]
    ),
    RateLimit(
        limit_id=EXCHANGE_INFO_PATH_URL,
        limit=1200,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(IP_REQUEST_RATE_LIMIT, 1)]
    ),
    RateLimit(
        limit_id=SERVER_TIME_PATH_URL,
        limit=1200,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(IP_REQUEST_RATE_LIMIT, 1)]
    ),
    RateLimit(
        limit_id=ACCOUNTS_PATH_URL,
        limit=900,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(UID_REQUEST_RATE_LIMIT, 1)]
    ),
    RateLimit(
        limit_id=MY_TRADES_PATH_URL,
        limit=900,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(UID_REQUEST_RATE_LIMIT, 1)]
    ),
    RateLimit(
        limit_id=ORDER_PATH_URL,
        limit=900,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(UID_REQUEST_RATE_LIMIT, 1)]
    ),
]

