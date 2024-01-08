from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "bitrue_main"

HBOT_ORDER_ID_PREFIX = "btr-"
MAX_ORDER_ID_LEN = 32

# Base URL
REST_URL = "https://openapi.bitrue.com/api/"
LISTEN_KEY_URL = "https://open.bitrue.com/poseidon/api"
WSS_PUBLIC_URL = "wss://ws.bitrue.com/market/ws"
WSS_PRIVATE_URL = "wss://wsapi.bitrue.com"

PUBLIC_API_VERSION = "v1"
PRIVATE_API_VERSION = "v1"
PRIVATE_API_VERSION_V2 = "v2"   # for myTrades endpoint

# Public API endpoints or BitrueClient function
TICKER_PRICE_CHANGE_PATH_URL = "/ticker/price"
TICKER_BOOK_PATH_URL = "/ticker/24hr"
EXCHANGE_INFO_PATH_URL = "/exchangeInfo"
PING_PATH_URL = "/time"
SNAPSHOT_PATH_URL = "/depth"
SERVER_TIME_PATH_URL = "/time"

# Private API endpoints or BitrueClient function
ACCOUNTS_PATH_URL = "/account"
MY_TRADES_PATH_URL = "/myTrades"
ORDER_PATH_URL = "/order"
USER_STREAM_PATH_URL = "/listenKey"

WS_HEARTBEAT_TIME_INTERVAL = 15

# Bitrue params

SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

TIME_IN_FORCE_GTC = "GTC"  # Good till cancelled
TIME_IN_FORCE_IOC = "IOC"  # Immediate or cancel
TIME_IN_FORCE_FOK = "FOK"  # Fill or kill

# Order States
ORDER_STATE = {
    "PENDING_CREATE": OrderState.PENDING_CREATE,
    "NEW": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "PENDING_CANCEL": OrderState.OPEN,
    "CANCELED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.FAILED,
}

# enumerated order states via websocket order updates
ORDER_STATE_WS = {
    0: OrderState.PENDING_CREATE,
    1: OrderState.OPEN,
    2: OrderState.FILLED,
    3: OrderState.PARTIALLY_FILLED,
    4: OrderState.CANCELED,
}

# enumerated order events via websocket order updates
ORDER_EVENT = {
    1: "NEW",
    2: "CANCELED",
    3: "TRADE",
    4: "CANCELED",
}

# Websocket event types
SNAPSHOT_EVENT_TYPE = "simple_depth"

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS = "ORDERS"
ORDERS_24HR = "ORDERS_24HR"
RAW_REQUESTS = "RAW_REQUESTS"

# Rate Limit time intervals
ONE_SECOND = 1
ONE_MINUTE = 60
ONE_DAY = 86400

MAX_REQUEST = 5000

RATE_LIMITS = [
    # Pools
    RateLimit(limit_id=REQUEST_WEIGHT, limit=1200, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS, limit=50, time_interval=10 * ONE_SECOND),
    RateLimit(limit_id=ORDERS_24HR, limit=160000, time_interval=ONE_DAY),
    RateLimit(limit_id=RAW_REQUESTS, limit=6100, time_interval= 5 * ONE_MINUTE),
    # Weighted Limits
    RateLimit(limit_id=TICKER_PRICE_CHANGE_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=TICKER_BOOK_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 2),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 50),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=USER_STREAM_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=PING_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=MY_TRADES_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 2),
                             LinkedLimitWeightPair(ORDERS, 1),
                             LinkedLimitWeightPair(ORDERS_24HR, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)])
]

ORDER_NOT_EXIST_ERROR_CODES = [-2013]
UNKNOWN_ORDER_ERROR_CODES = [-2010, -2011]
TIME_SYNC_ERROR_CODES = [-1021, -1022, -1102]
