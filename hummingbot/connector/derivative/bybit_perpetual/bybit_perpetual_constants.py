from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.common import OrderType, PositionMode
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "bybit_perpetual"

DEFAULT_DOMAIN = "bybit_perpetual_main"

HBOT_ORDER_ID_PREFIX = "BYBIT-"

REST_API_VERSION = "v5"

HBOT_BROKER_ID = "Hummingbot"

DEFAULT_TIME_IN_FORCE = "GTC"

AUTH_TOKEN_EXPIRATION = 60 * 2

REST_URLS = {
    "bybit_perpetual_main": "https://api.bybit.com/",
    "bybit_perpetual_testnet": "https://api-testnet.bybit.com/"
}

WSS_PUBLIC_URL_LINEAR = {
    "bybit_perpetual_main": "wss://stream.bybit.com/v5/public/linear",
    "bybit_perpetual_testnet": "wss://stream-testnet.bybit.com/v5/public/linear"
}

WSS_PUBLIC_URL_NON_LINEAR = {
    "bybit_perpetual_main": "wss://stream.bybit.com/v5/public/inverse",
    "bybit_perpetual_testnet": "wss://stream-testnet.bybit.com/v5/public/inverse"
}

WSS_PRIVATE_URL_LINEAR = WSS_PRIVATE_URL_NON_LINEAR = WSS_PRIVATE_URL = {
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
SET_LEVERAGE_PATH_URL = "/v5/position/set-leverage"
TRADE_HISTORY_PATH_URL = "/v5/execution/list"
GET_POSITIONS_PATH_URL = "/v5/position/list"

# Funding Settlement Time Span
FUNDING_SETTLEMENT_DURATION = (5, 5)  # seconds before snapshot, seconds after snapshot

# WebSocket Public Endpoints
WS_ORDER_BOOK_DEPTH = 200
WS_ORDER_BOOK_EVENTS_TOPIC = "orderBook_200.100ms"
WS_TRADES_TOPIC = "trade"
WS_INSTRUMENTS_INFO_TOPIC = "instrument_info.100ms"
WS_AUTHENTICATE_USER_ENDPOINT_NAME = "auth"
WS_SUBSCRIPTION_POSITIONS_ENDPOINT_NAME = "position"
WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME = "order"
WS_SUBSCRIPTION_EXECUTIONS_ENDPOINT_NAME = "execution"
WS_SUBSCRIPTION_WALLET_ENDPOINT_NAME = "wallet"

PRIVATE_ORDER_CHANNEL = "order"
PRIVATE_TRADE_CHANNEL = "trade"
PRIVATE_WALLET_CHANNEL = "wallet"
PRIVATE_POSITIONS_CHANNEL = "position"

# Websocket event types
# https://bybit-exchange.github.io/docs/v5/websocket/public/trade
TRADE_EVENT_TYPE = "snapshot"  # Weird but true in V5
SNAPSHOT_EVENT_TYPE = "depth"
# V5: https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook
ORDERBOOK_DIFF_EVENT_TYPE = "delta"
ORDERBOOK_SNAPSHOT_EVENT_TYPE = "snapshot"
TICKERS_SNAPSHOT_EVENT_TYPE = "snapshot"
TICKERS_DIFF_EVENT_TYPE = "delta"

# Order States
# https://bybit-exchange.github.io/docs/v5/enum#orderstatus
ORDER_STATE = {
    "New": OrderState.OPEN,
    "PartiallyFilled": OrderState.PARTIALLY_FILLED,
    "PartiallyFilledCanceled": OrderState.CANCELED,
    "Filled": OrderState.FILLED,
    "Cancelled": OrderState.CANCELED,
    "Rejected": OrderState.FAILED
}

ACCOUNT_TYPE = {
    "REGULAR": 1,
    "UNIFIED": 3,
    "UTA_PRO": 4
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
RET_CODE_MODE_NOT_MODIFIED = 110025
RET_CODE_MODE_ORDER_NOT_EMPTY = 30086
RET_CODE_API_KEY_EXPIRED = 33004
RET_CODE_LEVERAGE_NOT_MODIFIED = 110043
RET_CODE_POSITION_ZERO = 130125

API_REQUEST_RETRY = 2

UPDATE_TRADE_HISTORY_LIMIT = 200

# Rate Limit Type
REQUEST_GET_POST_SHARED = "ALL"

# Rate Limit time intervals
TWO_MINUTES = 120
ONE_SECOND = 1
SIX_SECONDS = 6
FIVE_SECONDS = 5
ONE_DAY = 60 * 60 * 24
ONE_HOUR = 60 * 60

# https://bybit-exchange.github.io/docs/v5/rate-limit#api-rate-limit-rules-for-vipspros
MAX_REQUEST_SECURE_DIVIDER = 1.5  # TODO: Cross-verify this with dev team
MAX_REQUEST_LIMIT_DEFAULT = 10 / MAX_REQUEST_SECURE_DIVIDER  # 20/s is the max

# No more than 600 requests are allowed in any 5-second window.
# https://bybit-exchange.github.io/docs/v5/rate-limit#ip-rate-limit
SHARED_RATE_LIMIT = 600  # per 5 second

RATE_LIMITS = {
    # General Limits on REST Verbs (GET/POST)
    RateLimit(
        limit_id=REQUEST_GET_POST_SHARED,
        limit=SHARED_RATE_LIMIT,
        time_interval=FIVE_SECONDS
    ),
    # Linked limits
    RateLimit(
        limit_id=LAST_TRADED_PRICE_PATH,
        limit=MAX_REQUEST_LIMIT_DEFAULT,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET_POST_SHARED),
        ]
    ),
    RateLimit(
        limit_id=GET_POSITIONS_PATH_URL,
        limit=MAX_REQUEST_LIMIT_DEFAULT,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET_POST_SHARED),
        ]
    ),
    RateLimit(
        limit_id=FUNDING_RATE_PATH_URL,
        limit=MAX_REQUEST_LIMIT_DEFAULT,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET_POST_SHARED),
        ]
    ),
    RateLimit(
        limit_id=TRADE_HISTORY_PATH_URL,
        limit=MAX_REQUEST_LIMIT_DEFAULT,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET_POST_SHARED),
        ]
    ),
    RateLimit(
        limit_id=TICKERS_PATH_URL,
        limit=MAX_REQUEST_LIMIT_DEFAULT,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET_POST_SHARED),
        ]
    ),
    RateLimit(
        limit_id=RECENT_TRADING_HISTORY_PATH_URL,
        limit=MAX_REQUEST_LIMIT_DEFAULT,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET_POST_SHARED),
        ]
    ),
    RateLimit(
        limit_id=SET_POSITION_MODE_PATH_URL,
        limit=MAX_REQUEST_LIMIT_DEFAULT,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET_POST_SHARED),
        ]
    ),
    RateLimit(
        limit_id=SET_LEVERAGE_PATH_URL,
        limit=MAX_REQUEST_LIMIT_DEFAULT,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET_POST_SHARED),
        ]
    ),
    RateLimit(
        limit_id=EXCHANGE_INFO_PATH_URL,
        limit=MAX_REQUEST_LIMIT_DEFAULT,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET_POST_SHARED),
        ]
    ),
    RateLimit(
        limit_id=ORDERBOOK_SNAPSHOT_PATH_URL,
        limit=MAX_REQUEST_LIMIT_DEFAULT,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET_POST_SHARED),
        ]
    ),
    RateLimit(
        limit_id=SERVER_TIME_PATH_URL,
        limit=MAX_REQUEST_LIMIT_DEFAULT,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET_POST_SHARED),
        ]
    ),
    RateLimit(
        limit_id=ORDER_PLACE_PATH_URL,
        limit=MAX_REQUEST_LIMIT_DEFAULT,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET_POST_SHARED),
        ]
    ),
    RateLimit(
        limit_id=ORDER_CANCEL_PATH_URL,
        limit=MAX_REQUEST_LIMIT_DEFAULT,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET_POST_SHARED),
        ]
    ),
    RateLimit(
        limit_id=GET_ORDERS_PATH_URL,
        limit=MAX_REQUEST_LIMIT_DEFAULT,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET_POST_SHARED),
        ]
    ),
    RateLimit(
        limit_id=ACCOUNT_INFO_PATH_URL,
        limit=MAX_REQUEST_LIMIT_DEFAULT,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET_POST_SHARED),
        ]
    ),
    RateLimit(
        limit_id=WALLET_BALANCE_PATH_URL,
        limit=MAX_REQUEST_LIMIT_DEFAULT,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_GET_POST_SHARED),
        ]
    ),
}
