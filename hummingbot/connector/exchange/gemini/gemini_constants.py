from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

# Base URLs
REST_URL = "https://api.gemini.com"
# Production WebSocket host. Per Gemini's docs (developer.gemini.com/websocket) the
# canonical host is wss://ws.gemini.com; it speaks the {id, method, params} subscribe
# protocol with the @-separated stream names defined below.
WSS_URL = "wss://ws.gemini.com"

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

# WebSocket order entry params (the WS API uses different enums than the v1 REST API:
# side/type/timeInForce are uppercase, and maker-or-cancel is expressed as timeInForce=MOC)
WS_SIDE_BUY = "BUY"
WS_SIDE_SELL = "SELL"
WS_ORDER_TYPE_LIMIT = "LIMIT"
WS_TIME_IN_FORCE_GTC = "GTC"
WS_TIME_IN_FORCE_MOC = "MOC"

# Seconds to wait for the {id, status, result|error} ack of a WS order request
# before treating the websocket path as failed and falling back to REST.
WS_ORDER_REQUEST_TIMEOUT = 10.0
# Seconds allowed for the trade websocket handshake. Connecting holds the trade WS
# lock, so an un-timeboxed connect would head-of-line block order placement/cancels.
WS_CONNECT_TIMEOUT = 10.0
# After a failed trade websocket connect, route orders straight to REST for this many
# seconds instead of letting every queued request serially retry the handshake.
WS_CONNECT_COOLDOWN = 30.0

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
# The WS API rejects cancels of unknown/filled orders with
# "Invalid parameters - order not found or already filled" (code -1013)
WS_ORDER_NOT_FOUND_MESSAGE = "order not found"


def convert_timestamp_to_seconds(ts: float) -> float:
    """Convert a Gemini Fast API timestamp to seconds.
    The Fast API uses nanoseconds for trade/order events and milliseconds for balance updates."""
    if ts > 1e15:
        return ts / 1e9
    elif ts > 1e11:
        return ts / 1e3
    return ts


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
