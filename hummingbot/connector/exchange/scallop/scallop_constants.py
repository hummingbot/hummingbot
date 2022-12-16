import sys

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "scallop"
DEFAULT_DOMAIN = ""
HBOT_BROKER_ID = "hummingbot"
HBOT_ORDER_ID_PREFIX = ""

# Base URL
REST_URL = "https://openapi.scallop.exchange/sapi/v1"
WSS_URL = "wss://wspool.hiotc.pro/kline-api/ws"

# Public API endpoints or ScallopClient function
PING_PATH_URL = "/ping"
SERVER_TIME_PATH_URL = "/time"
EXCHANGE_INFO_PATH_URL = "/symbols"
SNAPSHOT_PATH_URL = "/depth"
TRADES_PATH_URL = "/trades"
TICKER_PATH_URL = "/ticker"

# Private API endpoints or ScallopClient function
ACCOUNT_PATH_URL = "/account"
ORDER_PATH_URL = "/order"
OPEN_ORDERS_PATH_URL = "/openOrders"
MY_TRADES_PATH_URL = "/myTrades"
CREAT_ORDER_PATH_URL = "/order"
CREATE_BATCH_ORDERS_PATH_URL = "/batchOrders"
CANCEL_ORDER_PATH_URL = "/cancel"
CANCEL_BATCH_ORDERS_PATH_URL = "/batchCancel"

# websocket channels
SNAPSHOT_CHANNEL_SUFFIX = "depth_step0"
TRADE_CHANNEL_SUFFIX = "trade_ticker"

WS_HEARTBEAT_TIME_INTERVAL = 30

# Scallop params
SIDE_BUY = 'BUY'
SIDE_SELL = 'SELL'

TIME_IN_FORCE_GTC = 'GTC'  # Good till cancelled
TIME_IN_FORCE_IOC = 'IOC'  # Immediate or cancel
TIME_IN_FORCE_FOK = 'FOK'  # Fill or kill

# Rate Limit time intervals
ONE_SECOND = 1
TWO_SECOND = 2

# Rate Limit Max request
MAX_REQUEST_PRIVATE_GET = 20
MAX_REQUEST_PRIVATE_POST = 100
MAX_REQUEST_BATCH_ORDER = 50
NO_LIMIT = sys.maxsize

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

# Scallop has a per method API limit
RATE_LIMITS = [
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=NO_LIMIT, time_interval=ONE_SECOND),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=NO_LIMIT, time_interval=ONE_SECOND),
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=NO_LIMIT, time_interval=ONE_SECOND),
    RateLimit(limit_id=TRADES_PATH_URL, limit=NO_LIMIT, time_interval=ONE_SECOND),
    RateLimit(limit_id=TICKER_PATH_URL, limit=NO_LIMIT, time_interval=ONE_SECOND),
    RateLimit(limit_id=ACCOUNT_PATH_URL, limit=MAX_REQUEST_PRIVATE_GET, time_interval=TWO_SECOND),
    RateLimit(limit_id=ORDER_PATH_URL, limit=MAX_REQUEST_PRIVATE_GET, time_interval=TWO_SECOND),
    RateLimit(limit_id=OPEN_ORDERS_PATH_URL, limit=MAX_REQUEST_PRIVATE_GET, time_interval=TWO_SECOND),
    RateLimit(limit_id=MY_TRADES_PATH_URL, limit=MAX_REQUEST_PRIVATE_GET, time_interval=TWO_SECOND),
    RateLimit(limit_id=CREAT_ORDER_PATH_URL, limit=MAX_REQUEST_PRIVATE_POST, time_interval=TWO_SECOND),
    RateLimit(limit_id=CREATE_BATCH_ORDERS_PATH_URL, limit=MAX_REQUEST_BATCH_ORDER, time_interval=TWO_SECOND),
    RateLimit(limit_id=CANCEL_ORDER_PATH_URL, limit=MAX_REQUEST_PRIVATE_POST, time_interval=TWO_SECOND),
    RateLimit(limit_id=CANCEL_BATCH_ORDERS_PATH_URL, limit=MAX_REQUEST_BATCH_ORDER, time_interval=TWO_SECOND),
]
