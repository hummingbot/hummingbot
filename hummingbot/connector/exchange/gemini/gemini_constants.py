from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "gemini"

# REST URLs
REST_URL = "https://api.gemini.com"
SANDBOX_REST_URL = "https://api.sandbox.gemini.com"

# WebSocket URLs
WSS_MARKET_DATA_URL = "wss://api.gemini.com/v2/marketdata"
WSS_ORDER_EVENTS_URL = "wss://api.gemini.com/v1/order/events"
SANDBOX_WSS_MARKET_DATA_URL = "wss://api.sandbox.gemini.com/v2/marketdata"
SANDBOX_WSS_ORDER_EVENTS_URL = "wss://api.sandbox.gemini.com/v1/order/events"

WS_HEARTBEAT_TIME_INTERVAL = 30
MAX_ORDER_ID_LEN = 100
HBOT_ORDER_ID_PREFIX = "HBOT-"

# REST API paths
SYMBOLS_PATH_URL = "/v1/symbols"
SYMBOL_DETAILS_PATH_URL = "/v1/symbols/details/{symbol}"
ORDER_BOOK_PATH_URL = "/v1/book/{symbol}"
TICKER_V2_PATH_URL = "/v2/ticker/{symbol}"
NEW_ORDER_PATH_URL = "/v1/order/new"
CANCEL_ORDER_PATH_URL = "/v1/order/cancel"
ORDER_STATUS_PATH_URL = "/v1/order/status"
ACTIVE_ORDERS_PATH_URL = "/v1/orders"
MY_TRADES_PATH_URL = "/v1/mytrades"
BALANCES_PATH_URL = "/v1/balances"
HEARTBEAT_PATH_URL = "/v1/heartbeat"

SIDE_BUY = "buy"
SIDE_SELL = "sell"

# Gemini order state -> Hummingbot OrderState
ORDER_STATE = {
    "accepted": OrderState.OPEN,
    "booked": OrderState.OPEN,
    "cancelled": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
    "closed": OrderState.FILLED,
}

# WebSocket event types
DIFF_EVENT_TYPE = "l2_updates"
TRADE_EVENT_TYPE = "trade"

# Rate limits: public 120/min, private 600/min
PUBLIC_RATE_LIMIT_ID = "PUBLIC_RATE_LIMIT"
PRIVATE_RATE_LIMIT_ID = "PRIVATE_RATE_LIMIT"

RATE_LIMITS = [
    RateLimit(limit_id=PUBLIC_RATE_LIMIT_ID, limit=120, time_interval=60),
    RateLimit(limit_id=PRIVATE_RATE_LIMIT_ID, limit=600, time_interval=60),
    # Public endpoints
    RateLimit(
        limit_id=SYMBOLS_PATH_URL,
        limit=120,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_RATE_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=SYMBOL_DETAILS_PATH_URL,
        limit=120,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_RATE_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=ORDER_BOOK_PATH_URL,
        limit=120,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_RATE_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=TICKER_V2_PATH_URL,
        limit=120,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_RATE_LIMIT_ID)],
    ),
    # Private endpoints
    RateLimit(
        limit_id=NEW_ORDER_PATH_URL,
        limit=600,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_RATE_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=CANCEL_ORDER_PATH_URL,
        limit=600,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_RATE_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=ORDER_STATUS_PATH_URL,
        limit=600,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_RATE_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=ACTIVE_ORDERS_PATH_URL,
        limit=600,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_RATE_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=MY_TRADES_PATH_URL,
        limit=600,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_RATE_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=BALANCES_PATH_URL,
        limit=600,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_RATE_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=HEARTBEAT_PATH_URL,
        limit=600,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_RATE_LIMIT_ID)],
    ),
]

ORDER_NOT_FOUND_ERROR = "OrderNotFound"
ORDER_NOT_FOUND_MESSAGE = "order not found"
