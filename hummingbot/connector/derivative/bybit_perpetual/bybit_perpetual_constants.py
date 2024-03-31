from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.common import OrderType, PositionMode
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "bybit_perpetual"

DEFAULT_DOMAIN = "bybit_perpetual_main"

HBOT_ORDER_ID_PREFIX = "BYBIT-"

REST_API_VERSION = "v5"

HBOT_BROKER_ID = "Hummingbot"

DEFAULT_TIME_IN_FORCE = "GoodTillCancel"

REST_URLS = {
    "bybit_perpetual_main": "https://api.bybit.com/",
    "bybit_perpetual_testnet": "https://api-testnet.bybit.com/"
}

WSS_PUBLIC_URL_LINEAR = {
    "bybit_perpetual_main": "wss://stream.bybit.com/v5/public/linear",
    "bybit_perpetual_testnet": "wss://stream-testnet.bybit.com/v5/public/linear"
}

WSS_PUBLIC_URL_INVERSE = {
    "bybit_perpetual_main": "wss://stream.bybit.com/v5/public/linear",
    "bybit_perpetual_testnet": "wss://stream-testnet.bybit.com/v5/public/linear"
}

WSS_PRIVATE_URL = {
    "bybit_perpetual_main": "wss://stream.bybit.com/v5/private",
    "bybit_perpetual_testnet": "wss://stream-testnet.bybit.com/v5/private"
}


# unit in millisecond and default value is 5,000) to specify how long an HTTP request is valid.
# It is also used to prevent replay attacks.
# https://bybit-exchange.github.io/docs/v5/guide#parameters-for-authenticated-endpoints
X_API_RECV_WINDOW = str(50000)

MAX_ID_LEN = 36
SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 30
POSITION_IDX_ONEWAY = 0
POSITION_IDX_HEDGE_BUY = 1
POSITION_IDX_HEDGE_SELL = 2

ORDER_TYPE_MAP = {
    OrderType.LIMIT: "Limit",
    OrderType.MARKET: "Market",
}

POSITION_MODE_API_ONEWAY = 0
POSITION_MODE_API_HEDGE = 3
POSITION_MODE_MAP = {
    PositionMode.ONEWAY: POSITION_MODE_API_ONEWAY,
    PositionMode.HEDGE: POSITION_MODE_API_HEDGE,
}

# REST API Public Endpoints
LINEAR_MARKET = "linear"
NON_LINEAR_MARKET = "non_linear"

# REST API Private Endpoints
GET_POSITIONS_PATH_URL = {
    LINEAR_MARKET: "private/linear/position/list",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/position/list"}
PLACE_ACTIVE_ORDER_PATH_URL = {
    LINEAR_MARKET: "private/linear/order/create",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/order/create"}
CANCEL_ACTIVE_ORDER_PATH_URL = {
    LINEAR_MARKET: "private/linear/order/cancel",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/order/cancel"}
CANCEL_ALL_ACTIVE_ORDERS_PATH_URL = {
    LINEAR_MARKET: "private/linear/order/cancelAll",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/order/cancelAll"}
QUERY_ACTIVE_ORDER_PATH_URL = {
    LINEAR_MARKET: "private/linear/order/search",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/order"}
USER_TRADE_RECORDS_PATH_URL = {
    LINEAR_MARKET: "private/linear/trade/execution/list",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/execution/list"}

# Public API endpoints
TICKERS_PATH_URL = "/v5/market/tickers"
LAST_TRADED_PRICE_PATH = "/v5/market/tickers"
EXCHANGE_INFO_PATH_URL = "/v5/market/instruments-info"
ORDERBOOK_SNAPSHOT_PATH_URL = "/v5/market/orderbook"
SERVER_TIME_PATH_URL = "/v5/market/time"
FUNDING_RATE_PATH_URL = "/v5/market/funding/history"
RECENT_TRADING_HISTORY_PATH_URL = "/v5/market/recent-trade"

# Private API endpoints
ACCOUNT_INFO_PATH_URL = "/v5/account/info"
WALLET_BALANCE_PATH_URL = "/v5/account/wallet-balance"
ORDER_PLACE_PATH_URL = "/v5/order/create"
ORDER_CANCEL_PATH_URL = "/v5/order/cancel"
GET_ORDERS_PATH_URL = "/v5/order/realtime"
SET_TPSL_MODE_PATH_URL = "/v5/position/set-tpsl-mode"
SET_POSITION_MODE_PATH_URL = "/v5/position/switch-mode"
GET_POSITION_PATH_URL = "/v5/position/list"
SET_LEVERAGE_PATH_URL = "/v5/position/set-leverage"
TRADE_HISTORY_PATH_URL = "/v5/execution/list"

# Funding Settlement Time Span
FUNDING_SETTLEMENT_DURATION = (5, 5)  # seconds before snapshot, seconds after snapshot

# WebSocket Public Endpoints
WS_ORDER_BOOK_DEPTH = 200
WS_PING_REQUEST = "ping"
WS_ORDER_BOOK_EVENTS_TOPIC = "orderBook_200.100ms"
WS_TRADES_TOPIC = "trade"
WS_INSTRUMENTS_INFO_TOPIC = "instrument_info.100ms"
WS_AUTHENTICATE_USER_ENDPOINT_NAME = "auth"
WS_SUBSCRIPTION_POSITIONS_ENDPOINT_NAME = "position"
WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME = "order"
WS_SUBSCRIPTION_EXECUTIONS_ENDPOINT_NAME = "execution"
WS_SUBSCRIPTION_WALLET_ENDPOINT_NAME = "wallet"

# Order States
# https://bybit-exchange.github.io/docs/v5/enum#orderstatus
ORDER_STATE = {
    "New": OrderState.OPEN,
    "PartiallyFilled": OrderState.PARTIALLY_FILLED,
    "Filled": OrderState.FILLED,
    "Cancelled": OrderState.CANCELED,
    "Rejected": OrderState.FAILED,
}

WS_HEARTBEAT_TIME_INTERVAL = 20

GET_LIMIT_ID = "GETLimit"
POST_LIMIT_ID = "POSTLimit"
GET_RATE = 49  # per second
POST_RATE = 19  # per second

NON_LINEAR_PRIVATE_BUCKET_100_LIMIT_ID = "NonLinearPrivateBucket100"
NON_LINEAR_PRIVATE_BUCKET_600_LIMIT_ID = "NonLinearPrivateBucket600"
NON_LINEAR_PRIVATE_BUCKET_75_LIMIT_ID = "NonLinearPrivateBucket75"
NON_LINEAR_PRIVATE_BUCKET_120_B_LIMIT_ID = "NonLinearPrivateBucket120B"
NON_LINEAR_PRIVATE_BUCKET_120_C_LIMIT_ID = "NonLinearPrivateBucket120C"

LINEAR_PRIVATE_BUCKET_100_LIMIT_ID = "LinearPrivateBucket100"
LINEAR_PRIVATE_BUCKET_600_LIMIT_ID = "LinearPrivateBucket600"
LINEAR_PRIVATE_BUCKET_75_LIMIT_ID = "LinearPrivateBucket75"
LINEAR_PRIVATE_BUCKET_120_A_LIMIT_ID = "LinearPrivateBucket120A"

# Request error codes
RET_CODE_OK = 0
RET_CODE_PARAMS_ERROR = 10001
RET_CODE_API_KEY_INVALID = 10003
RET_CODE_AUTH_TIMESTAMP_ERROR = 10021
RET_CODE_ORDER_NOT_EXISTS = 20001
RET_CODE_MODE_POSITION_NOT_EMPTY = 30082
RET_CODE_MODE_NOT_MODIFIED = 30083
RET_CODE_MODE_ORDER_NOT_EMPTY = 30086
RET_CODE_API_KEY_EXPIRED = 33004
RET_CODE_LEVERAGE_NOT_MODIFIED = 34036
RET_CODE_POSITION_ZERO = 130125

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

# Rate Limit time intervals
TWO_MINUTES = 120
ONE_SECOND = 1
SIX_SECONDS = 6
ONE_DAY = 86400

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
    RateLimit(
        limit_id=LAST_TRADED_PRICE_PATH,
        limit=MAX_REQUEST_GET,
        time_interval=TWO_MINUTES,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET, 1),
            LinkedLimitWeightPair(REQUEST_GET_BURST, 1),
            LinkedLimitWeightPair(REQUEST_GET_MIXED, 1)
        ]),
    RateLimit(
        limit_id=FUNDING_RATE_PATH_URL,
        limit=MAX_REQUEST_GET,
        time_interval=TWO_MINUTES,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET, 1),
            LinkedLimitWeightPair(REQUEST_GET_BURST, 1),
            LinkedLimitWeightPair(REQUEST_GET_MIXED, 1)
        ]),
    RateLimit(
        limit_id=TRADE_HISTORY_PATH_URL,
        limit=MAX_REQUEST_GET,
        time_interval=TWO_MINUTES,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET, 1),
            LinkedLimitWeightPair(REQUEST_GET_BURST, 1),
            LinkedLimitWeightPair(REQUEST_GET_MIXED, 1)
        ]),
    RateLimit(
        limit_id=TICKERS_PATH_URL,
        limit=MAX_REQUEST_GET,
        time_interval=TWO_MINUTES,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET, 1),
            LinkedLimitWeightPair(REQUEST_GET_BURST, 1),
            LinkedLimitWeightPair(REQUEST_GET_MIXED, 1)
        ]),
    RateLimit(
        limit_id=RECENT_TRADING_HISTORY_PATH_URL,
        limit=MAX_REQUEST_GET,
        time_interval=TWO_MINUTES,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET, 1),
            LinkedLimitWeightPair(REQUEST_GET_BURST, 1),
            LinkedLimitWeightPair(REQUEST_GET_MIXED, 1)
        ]),
    RateLimit(
        limit_id=SET_POSITION_MODE_PATH_URL,
        limit=MAX_REQUEST_POST,
        time_interval=TWO_MINUTES,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_POST, 1),
            LinkedLimitWeightPair(REQUEST_POST_BURST, 1),
            LinkedLimitWeightPair(REQUEST_POST_MIXED, 1)
        ]),
    RateLimit(
        limit_id=SET_LEVERAGE_PATH_URL,
        limit=MAX_REQUEST_POST,
        time_interval=TWO_MINUTES,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_POST, 1),
            LinkedLimitWeightPair(REQUEST_POST_BURST, 1),
            LinkedLimitWeightPair(REQUEST_POST_MIXED, 1)
        ]),
    RateLimit(
        limit_id=EXCHANGE_INFO_PATH_URL,
        limit=MAX_REQUEST_GET,
        time_interval=TWO_MINUTES,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET, 1),
            LinkedLimitWeightPair(REQUEST_GET_BURST, 1),
            LinkedLimitWeightPair(REQUEST_GET_MIXED, 1)
        ]),
    RateLimit(
        limit_id=ORDERBOOK_SNAPSHOT_PATH_URL,
        limit=MAX_REQUEST_GET,
        time_interval=TWO_MINUTES,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET, 1),
            LinkedLimitWeightPair(REQUEST_GET_BURST, 1),
            LinkedLimitWeightPair(REQUEST_GET_MIXED, 1)
        ]),
    RateLimit(
        limit_id=SERVER_TIME_PATH_URL,
        limit=MAX_REQUEST_GET,
        time_interval=TWO_MINUTES,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET, 1),
            LinkedLimitWeightPair(REQUEST_GET_BURST, 1),
            LinkedLimitWeightPair(REQUEST_GET_MIXED, 1)
        ]),
    RateLimit(
        limit_id=ORDER_PLACE_PATH_URL,
        limit=MAX_REQUEST_POST,
        time_interval=TWO_MINUTES,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_POST, 1),
            LinkedLimitWeightPair(REQUEST_POST_BURST, 1),
            LinkedLimitWeightPair(REQUEST_POST_MIXED, 1)
        ]),
    RateLimit(
        limit_id=ORDER_CANCEL_PATH_URL,
        limit=MAX_REQUEST_POST,
        time_interval=TWO_MINUTES,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_POST, 1),
            LinkedLimitWeightPair(REQUEST_POST_BURST, 1),
            LinkedLimitWeightPair(REQUEST_POST_MIXED, 1)
        ]),
    RateLimit(
        limit_id=GET_ORDERS_PATH_URL,
        limit=MAX_REQUEST_POST,
        time_interval=TWO_MINUTES,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_POST, 1),
            LinkedLimitWeightPair(REQUEST_POST_BURST, 1),
            LinkedLimitWeightPair(REQUEST_POST_MIXED, 1)
        ]),
    RateLimit(
        limit_id=ACCOUNT_INFO_PATH_URL,
        limit=MAX_REQUEST_POST,
        time_interval=TWO_MINUTES,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_POST, 1),
            LinkedLimitWeightPair(REQUEST_POST_BURST, 1),
            LinkedLimitWeightPair(REQUEST_POST_MIXED, 1)
        ]),
    RateLimit(
        limit_id=WALLET_BALANCE_PATH_URL,
        limit=MAX_REQUEST_POST,
        time_interval=TWO_MINUTES,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_POST, 1),
            LinkedLimitWeightPair(REQUEST_POST_BURST, 1),
            LinkedLimitWeightPair(REQUEST_POST_MIXED, 1)
        ]),
}
