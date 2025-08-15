from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "com.br"

HBOT_ORDER_ID_PREFIX = "55"
USER_AGENT = "HBOT"
MAX_ORDER_ID_LEN = 20

# Base URL
REST_URL = "https://api.foxbit.com.br"
REST_V2_URL = "https://api.foxbit.com.br/AP"
WSS_URL = "api.foxbit.com.br"

PUBLIC_API_VERSION = "v3"
PRIVATE_API_VERSION = "v3"

# Public API endpoints or FoxbitClient function
EXCHANGE_INFO_PATH_URL = "markets"
PING_PATH_URL = "system/time"
SNAPSHOT_PATH_URL = "markets/{}/orderbook"
SERVER_TIME_PATH_URL = "system/time"
INSTRUMENTS_PATH_URL = "GetInstruments"

# Private API endpoints or FoxbitClient function
ACCOUNTS_PATH_URL = "accounts"
MY_TRADES_PATH_URL = "trades"
ORDER_PATH_URL = "orders"
CANCEL_ORDER_PATH_URL = "orders/cancel"
GET_ORDER_BY_CLIENT_ID = "orders/by-client-order-id/{}"

WS_HEADER = {
    "Content-Type": "application/json",
    "User-Agent": USER_AGENT,
}

WS_MESSAGE_FRAME_TYPE = {
    "Request": 0,
    "Reply": 1,
    "Subscribe": 2,
    "Event": 3,
    "Unsubscribe": 4,
}

WS_MESSAGE_FRAME = {
    "m": 0,  # WS_MESSAGE_FRAME_TYPE
    "i": 0,  # Sequence Number
    "n": "",  # Endpoint
    "o": "",  # Message Payload
}

WS_HEARTBEAT_TIME_INTERVAL = 20

SIDE_BUY = 'BUY'
SIDE_SELL = 'SELL'

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
TWO_SECONDS = 2
ONE_DAY = 86400

# Order States
ORDER_STATE = {
    "PENDING": OrderState.PENDING_CREATE,
    "ACTIVE": OrderState.OPEN,
    "NEW": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "PENDING_CANCEL": OrderState.PENDING_CANCEL,
    "CANCELED": OrderState.CANCELED,
    "PARTIALLY_CANCELED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.FAILED,
    "Unknown": OrderState.PENDING_CREATE,
    "Working": OrderState.OPEN,
    "Rejected": OrderState.FAILED,
    "Canceled": OrderState.CANCELED,
    "Expired": OrderState.FAILED,
    "FullyExecuted": OrderState.FILLED,
}

# Websocket subscribe endpoint
WS_AUTHENTICATE_USER = "AuthenticateUser"
WS_SUBSCRIBE_ACCOUNT = "SubscribeAccountEvents"
WS_SUBSCRIBE_ORDER_BOOK = "SubscribeLevel2"
WS_SUBSCRIBE_TOB = "SubscribeLevel1"
WS_SUBSCRIBE_TRADES = "SubscribeTrades"

# Websocket response event types from Foxbit
# Market data events
WS_ORDER_BOOK_RESPONSE = "Level2UpdateEvent"
# Private order events
WS_ACCOUNT_POSITION = "AccountPositionEvent"
WS_ORDER_STATE = "OrderStateEvent"
WS_ORDER_TRADE = "OrderTradeEvent"
WS_TRADE_RESPONSE = "TradeDataUpdateEvent"

ORDER_BOOK_DEPTH = 10

RATE_LIMITS = [
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=6, time_interval=ONE_SECOND),
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=10, time_interval=TWO_SECONDS),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=5, time_interval=ONE_SECOND),
    RateLimit(limit_id=PING_PATH_URL, limit=5, time_interval=ONE_SECOND),
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=15, time_interval=ONE_SECOND),
    RateLimit(limit_id=MY_TRADES_PATH_URL, limit=5, time_interval=ONE_SECOND),
    RateLimit(limit_id=GET_ORDER_BY_CLIENT_ID, limit=30, time_interval=TWO_SECONDS),
    RateLimit(limit_id=CANCEL_ORDER_PATH_URL, limit=30, time_interval=TWO_SECONDS),
    RateLimit(limit_id=ORDER_PATH_URL, limit=30, time_interval=TWO_SECONDS),
    RateLimit(limit_id=INSTRUMENTS_PATH_URL, limit=750, time_interval=ONE_MINUTE),
]

# Error codes
ORDER_NOT_EXIST_MESSAGE = "HTTP status is 404"
