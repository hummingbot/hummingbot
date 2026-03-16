from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "limitless"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = None

DOMAIN = EXCHANGE_NAME

BASE_URL = "https://api.limitless.exchange"
WS_URL = "wss://ws.limitless.exchange"

CURRENCY = "USDC"

# Limitless uses the inner connector for all API calls.
# These path stubs exist only to satisfy ExchangePyBase's abstract properties.
EXCHANGE_INFO_URL = "/info"
PING_URL = "/info"
CREATE_ORDER_URL = "/order"
CANCEL_ORDER_URL = "/order"
ORDER_URL = "/order"
ACCOUNT_INFO_URL = "/account"
SNAPSHOT_REST_URL = "/orderbook"

# WS channel names
TRADES_ENDPOINT_NAME = "trades"
DEPTH_ENDPOINT_NAME = "orderbookUpdate"

USER_ORDERS_ENDPOINT_NAME = "orderUpdates"
USEREVENT_ENDPOINT_NAME = "userFills"

DIFF_EVENT_TYPE = "order_book_snapshot"
TRADE_EVENT_TYPE = "trades"

# Order states
ORDER_STATE = {
    "open": OrderState.OPEN,
    "submitted": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "canceled": OrderState.CANCELED,
    "cancelled": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
    "unknown": OrderState.PENDING_CREATE,
}

HEARTBEAT_TIME_INTERVAL = 30.0

# Conservative rate limits: 10 req/s = 600 per minute
MAX_REQUEST = 600
ALL_ENDPOINTS_LIMIT = "All"

ORDER_NOT_EXIST_MESSAGE = "not found"
UNKNOWN_ORDER_MESSAGE = "not found"

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=MAX_REQUEST, time_interval=60),
    RateLimit(limit_id=EXCHANGE_INFO_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=PING_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=CREATE_ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=CANCEL_ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ACCOUNT_INFO_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=SNAPSHOT_REST_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
]
