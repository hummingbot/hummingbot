import sys

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

DEFAULT_DOMAIN = "com"

# REST endpoints
WHITEBIT_BASE_URL = "https://whitebit.com/"

# Public Endpoints
WHITEBIT_SERVER_STATUS_PATH = "api/v4/public/ping"
WHITEBIT_SERVER_TIME_PATH = "api/v4/public/time"
WHITEBIT_INSTRUMENTS_PATH = "api/v2/public/markets"
WHITEBIT_TICKER_PATH = "api/v4/public/ticker"
WHITEBIT_ORDER_BOOK_PATH = "api/v4/public/orderbook"

# Private Endpoints
WHITEBIT_WS_AUTHENTICATION_TOKEN_PATH = "api/v4/profile/websocket_token"
WHITEBIT_BALANCE_PATH = "api/v4/trade-account/balance"
WHITEBIT_ORDER_CREATION_PATH = "api/v4/order/new"
WHITEBIT_ORDER_CANCEL_PATH = "api/v4/order/cancel"
WHITEBIT_ACTIVE_ORDER_STATUS_PATH = "api/v4/orders"
WHITEBIT_EXECUTED_ORDER_STATUS_PATH = "api/v4/trade-account/order/history"
WHITEBIT_ORDER_TRADES_PATH = "api/v4/trade-account/order"

ORDER_FILLS_REQUEST_INVALID_ORDER_ID_ERROR_CODE = 422

# WS endpoints
WHITEBIT_WS_URI = "wss://api.whitebit.com/ws"

WS_CONNECTION_LIMIT_ID = "WSConnection"
WS_REQUEST_LIMIT_ID = "WSRequest"
WHITEBIT_WS_PUBLIC_BOOKS_CHANNEL = "depth_update"
WHITEBIT_WS_PUBLIC_TRADES_CHANNEL = "trades_update"
WHITEBIT_WS_PRIVATE_BALANCE_CHANNEL = "balanceSpot_update"
WHITEBIT_WS_PRIVATE_TRADES_CHANNEL = "deals_update"
WHITEBIT_WS_PRIVATE_ORDERS_CHANNEL = "ordersPending_update"

MINUTE = 60
NO_LIMIT = sys.maxsize
MAX_REQUESTS_LIMIT = 100
WHITEBIT_GENERAL_RATE_LIMIT = "HTTPRequestGlobalLimit"

RATE_LIMITS = [
    RateLimit(WS_CONNECTION_LIMIT_ID, limit=100, time_interval=MINUTE),
    RateLimit(WS_REQUEST_LIMIT_ID, limit=NO_LIMIT, time_interval=1),
    RateLimit(WHITEBIT_GENERAL_RATE_LIMIT, limit=MAX_REQUESTS_LIMIT, time_interval=1),
    RateLimit(
        WHITEBIT_SERVER_STATUS_PATH,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(WHITEBIT_GENERAL_RATE_LIMIT)],
    ),
    RateLimit(
        WHITEBIT_SERVER_TIME_PATH,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(WHITEBIT_GENERAL_RATE_LIMIT)],
    ),
    RateLimit(
        WHITEBIT_INSTRUMENTS_PATH,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(WHITEBIT_GENERAL_RATE_LIMIT)],
    ),
    RateLimit(
        WHITEBIT_TICKER_PATH,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(WHITEBIT_GENERAL_RATE_LIMIT)],
    ),
    RateLimit(
        WHITEBIT_ORDER_BOOK_PATH,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(WHITEBIT_GENERAL_RATE_LIMIT)],
    ),
    RateLimit(
        WHITEBIT_BALANCE_PATH,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(WHITEBIT_GENERAL_RATE_LIMIT)],
    ),
    RateLimit(
        WHITEBIT_ORDER_CREATION_PATH,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(WHITEBIT_GENERAL_RATE_LIMIT)],
    ),
    RateLimit(
        WHITEBIT_ORDER_CANCEL_PATH,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(WHITEBIT_GENERAL_RATE_LIMIT)],
    ),
    RateLimit(
        WHITEBIT_ACTIVE_ORDER_STATUS_PATH,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(WHITEBIT_GENERAL_RATE_LIMIT)],
    ),
    RateLimit(
        WHITEBIT_EXECUTED_ORDER_STATUS_PATH,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(WHITEBIT_GENERAL_RATE_LIMIT)],
    ),
    RateLimit(
        WHITEBIT_ORDER_TRADES_PATH,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(WHITEBIT_GENERAL_RATE_LIMIT)],
    ),
    RateLimit(
        WHITEBIT_WS_AUTHENTICATION_TOKEN_PATH,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(WHITEBIT_GENERAL_RATE_LIMIT)],
    ),
]
