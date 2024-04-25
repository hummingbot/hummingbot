from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "bybit_main"

HBOT_ORDER_ID_PREFIX = "BYBIT-"
MAX_ORDER_ID_LEN = 32
HBOT_BROKER_ID = "Hummingbot"

SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

TIME_IN_FORCE_GTC = "GTC"
# Base URL
REST_URLS = {
    "bybit_main": "https://api.bybit.com",
    "bybit_testnet": "https://api-testnet.bybit.com"
}

WSS_PUBLIC_URL = {
    "bybit_main": "wss://stream.bybit.com/v5/public/spot",
    "bybit_testnet": "wss://stream-testnet.bybit.com/v5/public/spot"
}

WSS_PRIVATE_URL = {
    "bybit_main": "wss://stream.bybit.com/v5/private",
    "bybit_testnet": "wss://stream-testnet.bybit.com/v5/private"
}

# unit in millisecond and default value is 5,000) to specify how long an HTTP request is valid.
# It is also used to prevent replay attacks.
# https://bybit-exchange.github.io/docs/v5/guide#parameters-for-authenticated-endpoints
X_API_RECV_WINDOW = str(50000)

# https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook
SPOT_ORDER_BOOK_DEPTH = 50

TRADE_CATEGORY = "spot"

# Websocket event types
# https://bybit-exchange.github.io/docs/v5/websocket/public/trade
TRADE_EVENT_TYPE = "snapshot"  # Weird but true in V5
SNAPSHOT_EVENT_TYPE = "depth"
# V5: https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook
ORDERBOOK_DIFF_EVENT_TYPE = "delta"
ORDERBOOK_SNAPSHOT_EVENT_TYPE = "snapshot"

PRIVATE_ORDER_CHANNEL = "order"
PRIVATE_TRADE_CHANNEL = "trade"
PRIVATE_WALLET_CHANNEL = "wallet"

WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME = "order"
WS_SUBSCRIPTION_EXECUTIONS_ENDPOINT_NAME = "execution"
WS_SUBSCRIPTION_WALLET_ENDPOINT_NAME = "wallet"

# Public API endpoints
LAST_TRADED_PRICE_PATH = "/v5/market/tickers"
EXCHANGE_INFO_PATH_URL = "/v5/market/instruments-info"
SNAPSHOT_PATH_URL = "/v5/market/orderbook"
SERVER_TIME_PATH_URL = "/v5/market/time"

# Private API endpoints
ACCOUNT_INFO_PATH_URL = "/v5/account/info"
BALANCE_PATH_URL = "/v5/account/wallet-balance"
ORDER_PLACE_PATH_URL = "/v5/order/create"
ORDER_CANCEL_PATH_URL = "/v5/order/cancel"
GET_ORDERS_PATH_URL = "/v5/order/realtime"
TRADE_HISTORY_PATH_URL = "/v5/execution/list"


# Order States
# https://bybit-exchange.github.io/docs/v5/enum#orderstatus
ORDER_STATE = {
    "New": OrderState.OPEN,
    "PartiallyFilled": OrderState.PARTIALLY_FILLED,
    "Filled": OrderState.FILLED,
    "Cancelled": OrderState.CANCELED,
    "PartiallyFilledCanceled": OrderState.CANCELED,
    "Rejected": OrderState.FAILED,
}

ACCOUNT_TYPE = {
    "REGULAR": 1,
    "UNIFIED": 3,
    "UTA_PRO": 4
}

WS_HEARTBEAT_TIME_INTERVAL = 20

# Rate Limit Type
REQUEST_GET = "GET"
REQUEST_GET_BURST = "GET_BURST"
REQUEST_GET_MIXED = "GET_MIXED"
REQUEST_POST = "POST"
REQUEST_POST_BURST = "POST_BURST"
REQUEST_POST_MIXED = "POST_MIXED"

# Rate Limit Max request
MAX_REQUEST_GET = 6000
MAX_REQUEST_GET_BURST = 70
MAX_REQUEST_GET_MIXED = 400
MAX_REQUEST_POST = 2400
MAX_REQUEST_POST_BURST = 50
MAX_REQUEST_POST_MIXED = 270

# Request error codes
RET_CODE_OK = 0
RET_CODE_PARAMS_ERROR = 10001
RET_CODE_API_KEY_INVALID = 10003
RET_CODE_AUTH_TIMESTAMP_ERROR = 10021
RET_CODE_ORDER_NOT_EXISTS = 20001
RET_CODE_MODE_POSITION_NOT_EMPTY = 30082
RET_CODE_MODE_NOT_MODIFIED = 110025
RET_CODE_MODE_ORDER_NOT_EMPTY = 30086
RET_CODE_API_KEY_EXPIRED = 33004
RET_CODE_LEVERAGE_NOT_MODIFIED = 110043
RET_CODE_POSITION_ZERO = 130125

# Rate Limit time intervals
TWO_MINUTES = 120
ONE_SECOND = 1
SIX_SECONDS = 6
ONE_DAY = 60 * 60 * 24
ONE_HOUR = 60 * 60

# klpanagi additions
API_REQUEST_RETRY = 2

RATE_LIMITS = {
    # General
    RateLimit(limit_id=REQUEST_GET, limit=MAX_REQUEST_GET, time_interval=TWO_MINUTES),
    RateLimit(limit_id=REQUEST_GET_BURST, limit=MAX_REQUEST_GET_BURST, time_interval=ONE_SECOND),
    RateLimit(limit_id=REQUEST_GET_MIXED, limit=MAX_REQUEST_GET_MIXED, time_interval=SIX_SECONDS),
    RateLimit(limit_id=REQUEST_POST, limit=MAX_REQUEST_POST, time_interval=TWO_MINUTES),
    RateLimit(limit_id=REQUEST_POST_BURST, limit=MAX_REQUEST_POST_BURST, time_interval=ONE_SECOND),
    RateLimit(limit_id=REQUEST_POST_MIXED, limit=MAX_REQUEST_POST_MIXED, time_interval=SIX_SECONDS),
    # Linked limits
    RateLimit(limit_id=LAST_TRADED_PRICE_PATH, limit=MAX_REQUEST_GET, time_interval=TWO_MINUTES,
              linked_limits=[LinkedLimitWeightPair(REQUEST_GET, 1), LinkedLimitWeightPair(REQUEST_GET_BURST, 1),
                             LinkedLimitWeightPair(REQUEST_GET_MIXED, 1)]),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=MAX_REQUEST_GET, time_interval=TWO_MINUTES,
              linked_limits=[LinkedLimitWeightPair(REQUEST_GET, 1), LinkedLimitWeightPair(REQUEST_GET_BURST, 1),
                             LinkedLimitWeightPair(REQUEST_GET_MIXED, 1)]),
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=MAX_REQUEST_GET, time_interval=TWO_MINUTES,
              linked_limits=[LinkedLimitWeightPair(REQUEST_GET, 1), LinkedLimitWeightPair(REQUEST_GET_BURST, 1),
                             LinkedLimitWeightPair(REQUEST_GET_MIXED, 1)]),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=MAX_REQUEST_GET, time_interval=TWO_MINUTES,
              linked_limits=[LinkedLimitWeightPair(REQUEST_GET, 1), LinkedLimitWeightPair(REQUEST_GET_BURST, 1),
                             LinkedLimitWeightPair(REQUEST_GET_MIXED, 1)]),
    RateLimit(limit_id=ORDER_PLACE_PATH_URL, limit=MAX_REQUEST_GET, time_interval=TWO_MINUTES,
              linked_limits=[LinkedLimitWeightPair(REQUEST_POST, 1), LinkedLimitWeightPair(REQUEST_POST_BURST, 1),
                             LinkedLimitWeightPair(REQUEST_POST_MIXED, 1)]),
    RateLimit(limit_id=ORDER_CANCEL_PATH_URL, limit=MAX_REQUEST_GET, time_interval=TWO_MINUTES,
              linked_limits=[LinkedLimitWeightPair(REQUEST_POST, 1), LinkedLimitWeightPair(REQUEST_POST_BURST, 1),
                             LinkedLimitWeightPair(REQUEST_POST_MIXED, 1)]),
    RateLimit(limit_id=GET_ORDERS_PATH_URL, limit=MAX_REQUEST_GET, time_interval=TWO_MINUTES,
              linked_limits=[LinkedLimitWeightPair(REQUEST_POST, 1), LinkedLimitWeightPair(REQUEST_POST_BURST, 1),
                             LinkedLimitWeightPair(REQUEST_POST_MIXED, 1)]),
    RateLimit(limit_id=ACCOUNT_INFO_PATH_URL, limit=MAX_REQUEST_GET, time_interval=TWO_MINUTES,
              linked_limits=[LinkedLimitWeightPair(REQUEST_POST, 1), LinkedLimitWeightPair(REQUEST_POST_BURST, 1),
                             LinkedLimitWeightPair(REQUEST_POST_MIXED, 1)]),
    RateLimit(limit_id=BALANCE_PATH_URL, limit=MAX_REQUEST_GET, time_interval=TWO_MINUTES,
              linked_limits=[LinkedLimitWeightPair(REQUEST_POST, 1), LinkedLimitWeightPair(REQUEST_POST_BURST, 1),
                             LinkedLimitWeightPair(REQUEST_POST_MIXED, 1)]),
    RateLimit(
        limit_id=TRADE_HISTORY_PATH_URL,
        limit=MAX_REQUEST_GET,
        time_interval=TWO_MINUTES,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET, 1),
            LinkedLimitWeightPair(REQUEST_GET_BURST, 1),
            LinkedLimitWeightPair(REQUEST_GET_MIXED, 1)
        ]),
}
