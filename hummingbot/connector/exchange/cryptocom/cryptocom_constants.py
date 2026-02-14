from hummingbot.connector.constants import SECOND
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "main"

EXCHANGE_NAME = "cryptocom"
HBOT_ORDER_ID_PREFIX = "HBOT"
MAX_ORDER_ID_LEN = 32

REST_URL = "https://api.crypto.com/exchange/v1"
WSS_PUBLIC_URL = "wss://stream.crypto.com/exchange/v1/market"
WSS_PRIVATE_URL = "wss://stream.crypto.com/exchange/v1/market"

# Public API endpoints
TICKER_BOOK_PATH_URL = "/public/get-ticker"
EXCHANGE_INFO_PATH_URL = "/public/get-instruments"
PING_PATH_URL = "/public/get-time"
SNAPSHOT_PATH_URL = "/public/get-book"
TRADES_PATH_URL = "/public/get-trades"

# Private API endpoints
ACCOUNTS_PATH_URL = "/private/get-account-summary"
MY_TRADES_PATH_URL = "/private/get-order-detail"
ORDER_PATH_URL = "/private/create-order"
CANCEL_ORDER_PATH_URL = "/private/cancel-order"
ORDER_DETAIL_PATH_URL = "/private/get-order-detail"

WS_HEARTBEAT_TIME_INTERVAL = 30

SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

TIME_IN_FORCE_GTC = "GOOD_TILL_CANCEL"

ORDER_STATE = {
    "ACTIVE": OrderState.OPEN,
    "OPEN": OrderState.OPEN,
    "PENDING": OrderState.PENDING_CREATE,
    "PENDING_CANCEL": OrderState.PENDING_CANCEL,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "FILLED": OrderState.FILLED,
    "CANCELED": OrderState.CANCELED,
    "CANCELLED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.FAILED,
    "FAILED": OrderState.FAILED,
}

DIFF_EVENT_TYPE = "book"
TRADE_EVENT_TYPE = "trade"

RAW_REQUESTS = "raw_requests"
REQUEST_WEIGHT = "request_weight"

RATE_LIMITS = [
    RateLimit(limit_id=RAW_REQUESTS, limit=100, time_interval=SECOND),
    RateLimit(limit_id=REQUEST_WEIGHT, limit=100, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(RAW_REQUESTS)]),
    RateLimit(limit_id=PING_PATH_URL, limit=100, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT)]),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=100, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT)]),
    RateLimit(limit_id=TICKER_BOOK_PATH_URL, limit=100, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT)]),
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=100, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT)]),
    RateLimit(limit_id=TRADES_PATH_URL, limit=100, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT)]),
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=100, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT)]),
    RateLimit(limit_id=MY_TRADES_PATH_URL, limit=100, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT)]),
    RateLimit(limit_id=ORDER_PATH_URL, limit=100, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT)]),
    RateLimit(limit_id=CANCEL_ORDER_PATH_URL, limit=100, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT)]),
    RateLimit(limit_id=ORDER_DETAIL_PATH_URL, limit=100, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT)]),
]

ORDER_NOT_EXIST_ERROR_CODE = 40032
ORDER_NOT_EXIST_MESSAGE = "Order is not found"
UNKNOWN_ORDER_ERROR_CODE = 40032
UNKNOWN_ORDER_MESSAGE = "Order is not found"
