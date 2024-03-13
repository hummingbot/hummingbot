from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState, OrderType

EXCHANGE_NAME = "cube"

DEFAULT_DOMAIN = "live"
TESTNET_DOMAIN = "staging"

HBOT_ORDER_ID_PREFIX = "x-HBCUBE"
MAX_ORDER_ID_LEN = 32

# Base URL
REST_URL = {"live": "https://api.cube.exchange",
            "staging": "https://staging.cube.exchange"}

# INFO_REQUEST_URL = "/ir/v0"
TRADE_REQUEST_URL = "/os/v0"
MARKET_DATA_REQUEST_URL = "/md/v0"

WSS_MARKET_DATA_URL = {"live": "wss://api.cube.exchange/md",
                       "staging": "wss://staging.cube.exchange/md"}

WSS_TRADE_URL = {"live": "wss://api.cube.exchange/os",
                 "staging": "wss://api.cube.exchange/os"}

EXCHANGE_INFO_PATH_URL = "/ir/v0/markets"
PING_PATH_URL = "/md/v0/parsed/tickers"
TICKER_BOOK_PATH_URL = "/md/v0/parsed/tickers"
ACCOUNTS_PATH_URL = "/ir/v0/users/positions"
ORDER_PATH_URL = "/ir/v0/users/orders"
FILLS_PATH_URL = "/ir/v0/users/fills"
POST_ORDER_PATH_URL = "/os/v0/order"

WS_HEARTBEAT_TIME_INTERVAL = 20

# Websocket channels
TRADE_EVENT_TYPE = "trades"
DIFF_EVENT_TYPE = "mbp_diff"
SNAPSHOT_EVENT_TYPE = "mbp_snapshot"

# Rate Limit ID
SNAPSHOT_LM_ID = "snapshot_rate_limit"
USER_STREAM_LM_ID = "user_stream_rate_limit"

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS = "ORDERS"
ORDERS_24HR = "ORDERS_24HR"
RAW_REQUESTS = "RAW_REQUESTS"

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 300

# Order States
ORDER_STATE = {
    "open": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "pfilled": OrderState.PARTIALLY_FILLED,
    "canceled": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
}

# Order Types
CUBE_ORDER_TYPE = {
    OrderType.LIMIT: 0,
    OrderType.LIMIT_MAKER: 0,
    OrderType.MARKET: 2,
}

# Order Side
SIDE_BUY = 0
SIDE_SELL = 1

# Time in force
TIME_IN_FORCE_IOC = 0
TIME_IN_FORCE_GTC = 1
TIME_IN_FORCE_FOK = 2

# Rate Limits
RATE_LIMITS = [
    RateLimit(limit_id=REQUEST_WEIGHT, limit=6000, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS, limit=50, time_interval=10 * ONE_SECOND),
    RateLimit(limit_id=ORDERS_24HR, limit=160000, time_interval=ONE_DAY),
    RateLimit(limit_id=RAW_REQUESTS, limit=61000, time_interval= 5 * ONE_MINUTE),
    # Weighted Limits
    RateLimit(limit_id=TICKER_BOOK_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 4),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 20),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=SNAPSHOT_LM_ID, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 100),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=USER_STREAM_LM_ID, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 2),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=PING_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 20),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=FILLS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 20),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 4),
                             LinkedLimitWeightPair(ORDERS, 1),
                             LinkedLimitWeightPair(ORDERS_24HR, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=POST_ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 4),
                             LinkedLimitWeightPair(ORDERS, 1),
                             LinkedLimitWeightPair(ORDERS_24HR, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)])
]
