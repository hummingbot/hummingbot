from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

# Base URLs
REST_URL = "https://api.gemini.com"
WSS_FAST_API_URL = "wss://wsapi.fast.gemini.com"

# REST API versions / paths
# Public
SYMBOLS_PATH_URL = "/v1/symbols"
SYMBOL_DETAILS_PATH_URL = "/v1/symbols/details/{}"
TICKER_PATH_URL = "/v2/ticker/{}"
ORDER_BOOK_PATH_URL = "/v1/book/{}"

# Private
NEW_ORDER_PATH_URL = "/v1/order/new"
CANCEL_ORDER_PATH_URL = "/v1/order/cancel"
ORDER_STATUS_PATH_URL = "/v1/order/status"
ACTIVE_ORDERS_PATH_URL = "/v1/orders"
MY_TRADES_PATH_URL = "/v1/mytrades"
BALANCES_PATH_URL = "/v1/balances"

# Fast API WebSocket methods
WS_METHOD_SUBSCRIBE = "subscribe"
WS_METHOD_UNSUBSCRIBE = "unsubscribe"
WS_METHOD_ORDER_PLACE = "order.place"
WS_METHOD_ORDER_CANCEL = "order.cancel"
WS_METHOD_ORDER_CANCEL_ALL = "order.cancel_all"
WS_METHOD_PING = "ping"
WS_METHOD_TIME = "time"

# Fast API stream channels
WS_DEPTH_STREAM = "{}@depth"
WS_DEPTH_PARTIAL_STREAM = "{}@depth{}"  # depth5, depth10, depth20
WS_TRADE_STREAM = "{}@trade"
WS_BOOK_TICKER_STREAM = "{}@bookTicker"
WS_ORDER_EVENTS_STREAM = "orders@account"
WS_BALANCE_STREAM = "balances@account"

# WebSocket event types
WS_EVENT_DEPTH_UPDATE = "depthUpdate"
WS_EVENT_TRADE = "trade"
WS_EVENT_ORDER_UPDATE = "executionReport"
WS_EVENT_BALANCE_UPDATE = "balanceUpdate"

# Hummingbot order ID
HBOT_ORDER_ID_PREFIX = "HBOT"
MAX_ORDER_ID_LEN = 36

# Order params
SIDE_BUY = "buy"
SIDE_SELL = "sell"
ORDER_TYPE_LIMIT = "exchange limit"
ORDER_TYPE_MARKET = "exchange market"

# Time
WS_HEARTBEAT_TIME_INTERVAL = 30

# Rate Limit IDs
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS_RATE = "ORDERS_RATE"

# Rate Limit intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 600

# Order States
ORDER_STATE = {
    "live": OrderState.OPEN,
    "accepted": OrderState.OPEN,
    "NEW": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "cancelled": OrderState.CANCELED,
    "CANCELED": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
    "REJECTED": OrderState.FAILED,
    "closed": OrderState.FILLED,
}

# Error codes
ORDER_NOT_FOUND_ERROR = "OrderNotFound"
INVALID_ORDER_ERROR = "InvalidOrderId"

RATE_LIMITS = [
    RateLimit(limit_id=REQUEST_WEIGHT, limit=600, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS_RATE, limit=100, time_interval=ONE_MINUTE),
    RateLimit(limit_id=SYMBOLS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=SYMBOL_DETAILS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=TICKER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=ORDER_BOOK_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=NEW_ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(ORDERS_RATE, 1)]),
    RateLimit(limit_id=CANCEL_ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(ORDERS_RATE, 1)]),
    RateLimit(limit_id=ORDER_STATUS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=ACTIVE_ORDERS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=MY_TRADES_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=BALANCES_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
]
