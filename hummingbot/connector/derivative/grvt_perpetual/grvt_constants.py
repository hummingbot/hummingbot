from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
try:
    from hummingbot.core.data_type.in_flight_order import OrderState
except Exception:  # pragma: no cover - fallback for lightweight environments
    from enum import Enum

    class OrderState(Enum):
        OPEN = "OPEN"
        PARTIALLY_FILLED = "PARTIALLY_FILLED"
        FILLED = "FILLED"
        CANCELED = "CANCELED"
        FAILED = "FAILED"

EXCHANGE_NAME = "grvt_perpetual"
DOMAIN = EXCHANGE_NAME
DEFAULT_DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "grvt_perpetual_testnet"
ORDER_ID_MAX_LEN = 36
HBOT_ORDER_ID_PREFIX = "grvt"

# NOTE:
# GRVT public docs are currently Cloudflare-blocked in this runtime.
# These endpoints are based on issue #8046 requirements and public comments.
GRVT_REST_BASE_URL = "https://api.grvt.io"
GRVT_WS_URL = "wss://api.grvt.io/ws"

SERVER_TIME_PATH_URL = "/v1/time"
INSTRUMENTS_PATH_URL = "/v1/instrument"
ORDER_BOOK_PATH_URL = "/v1/orderbook"
RECENT_TRADES_PATH_URL = "/v1/trades"
FUNDING_INFO_PATH_URL = "/v1/funding"

ACCOUNT_INFO_PATH_URL = "/v1/account"
POSITION_INFO_PATH_URL = "/v1/position"
SESSION_TOKEN_PATH_URL = "/v1/session"
CREATE_ORDER_PATH_URL = "/v1/order"
CANCEL_ORDER_PATH_URL = "/v1/order"
ORDER_STATUS_PATH_URL = "/v1/order"

WS_ORDER_BOOK_CHANNEL = "orderbook"
WS_TRADES_CHANNEL = "trades"
WS_FUNDING_CHANNEL = "funding"
WS_ORDERS_CHANNEL = "orders"
WS_FILLS_CHANNEL = "fills"
WS_POSITIONS_CHANNEL = "positions"
WS_ACCOUNT_CHANNEL = "account"

API_KEY_HEADER = "X-GRVT-API-KEY"
TIMESTAMP_HEADER = "X-GRVT-TIMESTAMP"
SIGNATURE_HEADER = "X-GRVT-SIGN"
SESSION_TOKEN_HEADER = "X-GRVT-TOKEN"

HEARTBEAT_TIME_INTERVAL = 30.0
MAX_REQUESTS_PER_MINUTE = 1200
ALL_ENDPOINTS_LIMIT = "ALL_ENDPOINTS"

ORDER_STATE = {
    "new": OrderState.OPEN,
    "open": OrderState.OPEN,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "filled": OrderState.FILLED,
    "cancelled": OrderState.CANCELED,
    "canceled": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
    "failed": OrderState.FAILED,
}

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=MAX_REQUESTS_PER_MINUTE, time_interval=60),
    RateLimit(
        limit_id=SERVER_TIME_PATH_URL,
        limit=MAX_REQUESTS_PER_MINUTE,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=INSTRUMENTS_PATH_URL,
        limit=MAX_REQUESTS_PER_MINUTE,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=ORDER_BOOK_PATH_URL,
        limit=MAX_REQUESTS_PER_MINUTE,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=RECENT_TRADES_PATH_URL,
        limit=MAX_REQUESTS_PER_MINUTE,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=FUNDING_INFO_PATH_URL,
        limit=MAX_REQUESTS_PER_MINUTE,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=ACCOUNT_INFO_PATH_URL,
        limit=MAX_REQUESTS_PER_MINUTE,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, 2)],
    ),
    RateLimit(
        limit_id=POSITION_INFO_PATH_URL,
        limit=MAX_REQUESTS_PER_MINUTE,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, 2)],
    ),
    RateLimit(
        limit_id=CREATE_ORDER_PATH_URL,
        limit=MAX_REQUESTS_PER_MINUTE,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, 5)],
    ),
    RateLimit(
        limit_id=CANCEL_ORDER_PATH_URL,
        limit=MAX_REQUESTS_PER_MINUTE,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, 3)],
    ),
    RateLimit(
        limit_id=ORDER_STATUS_PATH_URL,
        limit=MAX_REQUESTS_PER_MINUTE,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, 2)],
    ),
]
