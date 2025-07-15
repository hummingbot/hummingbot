from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "com"

HBOT_ORDER_ID_PREFIX = "xt-"
MAX_ORDER_ID_LEN = 32

# Base URL
REST_URL = "https://sapi.xt.{}/"
WSS_URL_PUBLIC = "wss://stream.xt.{}/public"
WSS_URL_PRIVATE = "wss://stream.xt.{}/private"

PUBLIC_API_VERSION = "v4"
PRIVATE_API_VERSION = "v4"

# Public REST API endpoints
TICKER_PRICE_CHANGE_PATH_URL = "/public/ticker/price"
EXCHANGE_INFO_PATH_URL = "/public/symbol"
SNAPSHOT_PATH_URL = "/public/depth"
SERVER_TIME_PATH_URL = "/public/time"

# Private REST API endpoints
ACCOUNTS_PATH_URL = "/balances"
MY_TRADES_PATH_URL = "/trade"
ORDER_PATH_URL = "/order"
OPEN_ORDER_PATH_URL = "open-order"
GET_ACCOUNT_LISTENKEY = "/ws-token"

WS_HEARTBEAT_TIME_INTERVAL = 15

# Websocket event types
DIFF_EVENT_TYPE = "depth_update"
TRADE_EVENT_TYPE = "trade"


# XT params
SIDE_BUY = 'BUY'
SIDE_SELL = 'SELL'

TIME_IN_FORCE_GTC = 'GTC'  # Good till cancelled
TIME_IN_FORCE_IOC = 'IOC'  # Immediate or cancel
TIME_IN_FORCE_FOK = 'FOK'  # Fill or kill

XT_VALIDATE_ALGORITHMS = "HmacSHA256"
XT_VALIDATE_RECVWINDOW = "5000"
XT_VALIDATE_CONTENTTYPE_URLENCODE = "application/x-www-form-urlencoded"
XT_VALIDATE_CONTENTTYPE_JSON = "application/json;charset=UTF-8"


# Order States
ORDER_STATE = {
    "PENDING": OrderState.PENDING_CREATE,
    "NEW": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "PENDING_CANCEL": OrderState.OPEN,
    "CANCELED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.FAILED,
}


# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

SINGLE_SYMBOL = 100
MULTIPLE_SYMBOLS = 10

# A single rate limit id for managing orders: GET open-orders, order/trade details, DELETE cancel order.
MANAGE_ORDER = "ManageOrder"

RATE_LIMITS = [
    RateLimit(limit_id=TICKER_PRICE_CHANGE_PATH_URL, limit=SINGLE_SYMBOL, time_interval=ONE_SECOND),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=MULTIPLE_SYMBOLS, time_interval=ONE_SECOND),
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=2 * SINGLE_SYMBOL, time_interval=ONE_SECOND),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=100, time_interval=ONE_SECOND),
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=MANAGE_ORDER, limit=500, time_interval=ONE_SECOND),
    RateLimit(limit_id=ORDER_PATH_URL, limit=50, time_interval=ONE_SECOND),
    RateLimit(limit_id=GET_ACCOUNT_LISTENKEY, limit=10, time_interval=ONE_SECOND)
]
