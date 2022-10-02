from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = ""

HBOT_ORDER_ID_PREFIX = "x-XEKWYICX"
MAX_ORDER_ID_LEN = 32

# Base URL
PUBLIC_REST_URL = "https://sapi.coinhub.mn/"
PRIVATE_REST_URL = "https://sapi3.coinhub.mn/"
WSS_URL = "wss://sapi.coinhub.mn/ws/"

PUBLIC_API_VERSION = "v1"
PRIVATE_API_VERSION = "v1"

# Public API endpoints or BinanceClient function
TICKER_PRICE_CHANGE_PATH_URL = "/market/tickers"
MARKET_LIST_PATH_URL = "/market/list"
PING_PATH_URL = "/ping"
SNAPSHOT_PATH_URL = "/market/depth"
SERVER_TIME_PATH_URL = "/time"

# Private API endpoints or BinanceClient function
WS_SIGN_PATH_URL = "/v1/api/sign"
ACCOUNTS_PATH_URL = "/api/balance/query"
MY_TRADES_PATH_URL = "/api/order/user_deals"
CREATE_ORDER_PATH_URL = "/api/order/create"
ORDER_CANCEL_PATH_URL = "/api/order/cancel"
GET_ORDER_PATH_URL = "/api/order/detail"
ORDER_FILLS_URL = "/api/order/order_deals"

COINHUB_USER_STREAM_PATH_URL = "/userDataStream"

WS_HEARTBEAT_TIME_INTERVAL = 30

# Binance params

SIDE_BUY = 2
SIDE_SELL = 1

TIME_IN_FORCE_GTC = "GTC"  # Good till cancelled
TIME_IN_FORCE_IOC = "IOC"  # Immediate or cancel
TIME_IN_FORCE_FOK = "FOK"  # Fill or kill

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS = "ORDERS"
ORDERS_24HR = "ORDERS_24HR"

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 5000

# Order States
ORDER_STATE = {
    "opened": OrderState.OPEN,
    "done": OrderState.FILLED,
}

# Websocket event types
DIFF_EVENT_TYPE = "depth.subscribe"
TRADE_EVENT_TYPE = "deals.subscribe"

RATE_LIMITS = [
    # Pools
    RateLimit(limit_id=REQUEST_WEIGHT, limit=1200, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=ORDERS_24HR, limit=100000, time_interval=ONE_DAY),
    # Weighted Limits
    RateLimit(
        limit_id=TICKER_PRICE_CHANGE_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 40)],
    ),
    RateLimit(
        limit_id=MARKET_LIST_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
        linked_limits=[(LinkedLimitWeightPair(REQUEST_WEIGHT, 10))],
    ),
    RateLimit(
        limit_id=SNAPSHOT_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 50)],
    ),
    RateLimit(
        limit_id=COINHUB_USER_STREAM_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)],
    ),
    RateLimit(
        limit_id=SERVER_TIME_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)],
    ),
    RateLimit(
        limit_id=PING_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)],
    ),
    RateLimit(
        limit_id=ACCOUNTS_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10)],
    ),
    RateLimit(
        limit_id=MY_TRADES_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10)],
    ),
    RateLimit(
        limit_id=CREATE_ORDER_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
            LinkedLimitWeightPair(ORDERS, 1),
            LinkedLimitWeightPair(ORDERS_24HR, 1),
        ],
    ),
    RateLimit(
        limit_id=ORDER_CANCEL_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
            LinkedLimitWeightPair(ORDERS, 1),
            LinkedLimitWeightPair(ORDERS_24HR, 1),
        ],
    ),
    RateLimit(
        limit_id=GET_ORDER_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
            LinkedLimitWeightPair(ORDERS, 1),
            LinkedLimitWeightPair(ORDERS_24HR, 1),
        ],
    ),
    RateLimit(
        limit_id=ORDER_FILLS_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
            LinkedLimitWeightPair(ORDERS, 1),
            LinkedLimitWeightPair(ORDERS_24HR, 1),
        ],
    ),
]
