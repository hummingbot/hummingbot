import sys

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "com"

REST_URL = "https://aincent.com/api/"
WSS_URL = "wss://aincent.com/api/{}/ws"
API_VERSION = "v1"

ORDER_ID_MAX_LEN = None
HBOT_ORDER_ID_PREFIX = ""

RECEIVE_WINDOW = 5000

# Public API endpoints
EXCHANGE_INFO_PATH_URL = "/exchangeInfo"
LAST_PRICE_URL = "/ticker/price"
SNAPSHOT_PATH_URL = "/depth"
SERVER_TIME_PATH_URL = "/time"
SERVER_AVAILABILITY_URL = "/ping"

# Private API endpoints
ACCOUNTS_PATH_URL = "/account"
MY_TRADES_PATH_URL = "/myTrades"
ORDER_PATH_URL = "/order"
USER_FEES_PATH_URL = "/account/commission"

# Order States
ORDER_STATE = {
    "ACTIVE": OrderState.OPEN,
    "OPEN": OrderState.OPEN,
    "CANCELED": OrderState.CANCELED,
    "FILLED": OrderState.FILLED,
    "EXPIRED": OrderState.FAILED,
    "FAILED": OrderState.FAILED,
}

WS_HEARTBEAT_TIME_INTERVAL = 30

# WebSocket methods
WS_SESSION_LOGON_METHOD = "session.logon"
WS_SESSION_SUBSCRIBE_METHOD = "session.subscribe"

# WebSocket event types
DIFF_EVENT_TYPE = "depthUpdate"
TRADE_EVENT_TYPE = "trade"

ONE_MINUTE = 60
MAX_REQUEST = sys.maxsize
RATE_LIMITS = [
    RateLimit(
        limit_id=EXCHANGE_INFO_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
    ),
    RateLimit(
        limit_id=LAST_PRICE_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
    ),
    RateLimit(
        limit_id=SNAPSHOT_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
    ),
    RateLimit(
        limit_id=SERVER_TIME_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
    ),
    RateLimit(
        limit_id=SERVER_AVAILABILITY_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
    ),
    RateLimit(
        limit_id=ACCOUNTS_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
    ),
    RateLimit(
        limit_id=MY_TRADES_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
    ),
    RateLimit(
        limit_id=ORDER_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
    ),
    RateLimit(
        limit_id=USER_FEES_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
    ),
]
