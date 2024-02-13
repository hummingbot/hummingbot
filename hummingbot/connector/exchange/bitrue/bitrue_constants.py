from hummingbot.connector.constants import MINUTE, SECOND
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

MAX_ORDER_ID_LEN = 32

DEFAULT_DOMAIN = ""

# Base URL
REST_URL = "https://openapi.bitrue.com/api/"
WSS_PUBLIC_URL = "wss://ws.bitrue.com/market/ws"
WSS_PRIVATE_URL = "wss://wsapi.bitrue.com"

API_VERSION = "v1"

HBOT_ORDER_ID_PREFIX = ""

ORDERBOOK_CHANNEL_PREFIX = "market_"
ORDERBOOK_CHANNEL_SUFFIX = "_simple_depth_step0"

# Public API endpoints
TICKER_PRICES_URL = "/ticker/price"
TICKER_PRICE_CHANGE_PATH_URL = "/ticker/24hr"
TICKER_BOOK_PATH_URL = "/ticker/bookTicker"
TICKER_BOOK_PATH_URL_SINGLE_SYMBOL_LIMIT_ID = f"{TICKER_BOOK_PATH_URL}::single_symbol"
EXCHANGE_INFO_PATH_URL = "/exchangeInfo"
PING_PATH_URL = "/ping"
SNAPSHOT_PATH_URL = "/depth"
SERVER_TIME_PATH_URL = "/time"

# Private API endpoints
ACCOUNTS_PATH_URL = "/account"
MY_TRADES_PATH_URL = "v2/myTrades"
ORDER_PATH_URL = "/order"
ALL_ORDERS_PATH_URL = "/allOrders"
OPEN_ORDERS_PATH_URL = "/openOrders"
BITRUE_USER_STREAM_PATH_URL = "/poseidon/api/v1/listenKey"

# Rate Limit IDs
CREATE_ORDER_RATE_LIMIT_ID = "BitrueCreateOrderRateLimitId"
CANCEL_ORDER_RATE_LIMIT_ID = "BitrueCancelOrderRateLimitId"
ORDER_STATUS_RATE_LIMIT_ID = "BitrueOrderStatusRateLimitId"


WS_HEARTBEAT_TIME_INTERVAL = 10
MAX_BATCH_ORDER_STATUS_ENTRY_LIMIT = 1000

SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

TIME_IN_FORCE_GTC = "GTC"  # Good till cancelled
TIME_IN_FORCE_IOC = "IOC"  # Immediate or cancel
TIME_IN_FORCE_FOK = "FOK"  # Fill or kill

# Rate Limit Type
GENERAL = "general"
ORDERS_IP = "orders_ip_seconds"
ORDERS_USER = "orders_user_seconds"

MAX_REQUEST = 20000

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

WS_ORDER_STATE = {
    0: OrderState.PENDING_CREATE,
    1: OrderState.OPEN,
    2: OrderState.FILLED,
    3: OrderState.PARTIALLY_FILLED,
    4: OrderState.CANCELED,
}

WS_CONNECTIONS_RATE_LIMIT = "WS_CONNECTIONS"

# Websocket event types
DIFF_EVENT_TYPE = "depthUpdate"
TRADE_EVENT_TYPE = "trade"
TICKER_EVENT_TYPE = "ticker"

BATCH_ORDERS_UPDATE_WEIGHT = 20
SINGLE_ORDER_UPDATE_WEIGHT = 4


RATE_LIMITS = [
    # Pools - will be updated in exchange info initialization
    RateLimit(limit_id=GENERAL, limit=MAX_REQUEST, time_interval=MINUTE),
    RateLimit(limit_id=ORDERS_IP, limit=750, time_interval=6 * SECOND),
    RateLimit(limit_id=ORDERS_USER, limit=200, time_interval=10 * SECOND),
    # Weighted Limits
    RateLimit(
        limit_id=TICKER_PRICE_CHANGE_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(GENERAL, 40)],
    ),
    RateLimit(
        limit_id=TICKER_BOOK_PATH_URL_SINGLE_SYMBOL_LIMIT_ID,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(GENERAL, 1)],
    ),
    RateLimit(
        limit_id=TICKER_BOOK_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(GENERAL, 1)],
    ),
    RateLimit(
        limit_id=EXCHANGE_INFO_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(GENERAL, 1)],
    ),
    RateLimit(
        limit_id=SNAPSHOT_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(GENERAL, 10)],
    ),
    RateLimit(
        limit_id=BITRUE_USER_STREAM_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(GENERAL, 1)],
    ),
    RateLimit(
        limit_id=SERVER_TIME_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(GENERAL, 1)],
    ),
    RateLimit(
        limit_id=PING_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(GENERAL, 1)],
    ),
    RateLimit(
        limit_id=ACCOUNTS_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(ORDERS_IP, 5), LinkedLimitWeightPair(ORDERS_USER, 5)],
    ),
    RateLimit(
        limit_id=MY_TRADES_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(ORDERS_IP, 1), LinkedLimitWeightPair(ORDERS_USER, 1)],
    ),
    RateLimit(
        limit_id=CREATE_ORDER_RATE_LIMIT_ID,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(ORDERS_IP, 1), LinkedLimitWeightPair(ORDERS_USER, 1)],
    ),
    RateLimit(
        limit_id=CANCEL_ORDER_RATE_LIMIT_ID,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(ORDERS_IP, 1), LinkedLimitWeightPair(ORDERS_USER, 1)],
    ),
    RateLimit(
        limit_id=ORDER_STATUS_RATE_LIMIT_ID,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(ORDERS_IP, 1), LinkedLimitWeightPair(ORDERS_USER, 1)],
    ),
    RateLimit(
        limit_id=ALL_ORDERS_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(ORDERS_IP, 5), LinkedLimitWeightPair(ORDERS_USER, 5)],
    ),
    RateLimit(
        limit_id=OPEN_ORDERS_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(ORDERS_IP, 5), LinkedLimitWeightPair(ORDERS_USER, 5)],
    ),
    RateLimit(
        limit_id=WS_CONNECTIONS_RATE_LIMIT,
        limit=300,
        time_interval=5 * MINUTE,
    ),
]

ORDER_NOT_FOUND_ERROR_CODE = -2013
ORDER_NOT_FOUND_MESSAGE = "Could not find order information for given order ID."
