from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "com"

HBOT_ORDER_ID_PREFIX = "HBOT-"
MAX_ORDER_ID_LEN = 32

# Base URL
REST_URL = "https://api.crypto.com/exchange"
WSS_PRIVATE_URL = "wss://stream.crypto.com/exchange/v1/user"
WSS_PUBLIC_URL = "wss://stream.crypto.com/exchange/v1/market"

PUBLIC_API_VERSION = "v1"
PRIVATE_API_VERSION = "v1"

# Public API endpoints
TICKER_PRICE_CHANGE_PATH_URL = "public/get-tickers"
EXCHANGE_INFO_PATH_URL = "public/get-instruments"
PING_PATH_URL = "public/get-candlestick"
SNAPSHOT_PATH_URL = "public/get-book"

# Private API endpoints
CREATE_ORDER_PATH_URL = "private/create-order"
CANCEL_ORDER_PATH_URL = "private/cancel-order"
ACCOUNTS_PATH_URL = "private/user-balance"
ORDER_DETAIL_PATH_URL = "private/get-order-detail"
OPEN_ORDERS_PATH_URL = "private/get-open-orders"
TRADE_HISTORY_PATH_URL = "private/get-trades"

# Websocket endpoints
WS_AUTHENTICATE = "public/auth"
WS_SUBSCRIBE = "subscribe"
WS_PING = "public/heartbeat"
WS_PONG = "public/respond-heartbeat"
WS_TRADE_CHANNEL = "trade"
WS_SNAPSHOT_CHANNEL = "book"
WS_DIFF_CHANNEL = "book.update"
WS_USER_BALANCE_CHANNEL = "user.balance"
WS_USER_ORDER_CHANNEL = "user.order"
WS_USER_TRADE_CHANNEL = "user.trade"

WS_HEARTBEAT_TIME_INTERVAL = 30

# Crypto.com order params
SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

TIME_IN_FORCE_GTC = "GOOD_TILL_CANCEL"  # Good till cancelled
TIME_IN_FORCE_IOC = "IMMEDIATE_OR_CANCEL"  # Immediate or cancel
TIME_IN_FORCE_FOK = "FILL_OR_KILL"  # Fill or kill

# Order States
ORDER_STATE = {
    "PENDING": OrderState.PENDING_CREATE,
    "NEW": OrderState.OPEN,
    "ACTIVE": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "PENDING_CANCEL": OrderState.OPEN,
    "CANCELED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.FAILED,
}

RATE_LIMITS = [
    RateLimit(limit_id=TICKER_PRICE_CHANGE_PATH_URL, limit=100, time_interval=1),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=100, time_interval=1),
    RateLimit(limit_id=PING_PATH_URL, limit=100, time_interval=1),
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=100, time_interval=1),
    RateLimit(limit_id=CREATE_ORDER_PATH_URL, limit=15, time_interval=0.1),
    RateLimit(limit_id=CANCEL_ORDER_PATH_URL, limit=15, time_interval=0.1),
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=3, time_interval=0.1),
    RateLimit(limit_id=ORDER_DETAIL_PATH_URL, limit=30, time_interval=0.1),
    RateLimit(limit_id=OPEN_ORDERS_PATH_URL, limit=3, time_interval=0.1),
    RateLimit(limit_id=TRADE_HISTORY_PATH_URL, limit=1, time_interval=1),
    RateLimit(limit_id=WS_AUTHENTICATE, limit=150, time_interval=1),
    RateLimit(limit_id=WS_SUBSCRIBE, limit=150, time_interval=1),
    RateLimit(limit_id=WS_TRADE_CHANNEL, limit=100, time_interval=1),
    RateLimit(limit_id=WS_SNAPSHOT_CHANNEL, limit=100, time_interval=1),
    RateLimit(limit_id=WS_DIFF_CHANNEL, limit=100, time_interval=1),
    RateLimit(limit_id=WS_USER_BALANCE_CHANNEL, limit=150, time_interval=1),
    RateLimit(limit_id=WS_USER_ORDER_CHANNEL, limit=150, time_interval=1),
    RateLimit(limit_id=WS_USER_TRADE_CHANNEL, limit=150, time_interval=1),
]

ORDER_NOT_EXIST_ERROR_CODE = [307, 316, 40401]
