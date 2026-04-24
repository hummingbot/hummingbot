from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "evedex_perpetual"
DEFAULT_DOMAIN = "evedex_perpetual"

HBOT_ORDER_ID_PREFIX = "HBOT"
MAX_ORDER_ID_LEN = 32

# Chain ID
CHAIN_ID = "161803"

# EvedEx EIP-712 Constants
EVEDEX_DOMAIN_NAME = "EVEDEX"
EVEDEX_DOMAIN_VERSION = "2"
EVEDEX_DOMAIN_SALT = "0x5792f7333c35db190e30acc144f049fd15b24f552c0010b8b3e06f9105c37c5a"  # noqa: mock
MATCHER_PRECISION = 8  # Used for normalizing floating-point numbers

# Base URLs
REST_URL = "https://exchange-api.evedex.com"
WSS_URL = "wss://ws.evedex.com/connection/websocket"
AUTH_URL = "https://auth.evedex.com"

# Auth endpoints (SIWE - Sign-In with Ethereum)
AUTH_NONCE_PATH_URL = "/auth/nonce"
AUTH_SIGNUP_PATH_URL = "/auth/user/sign-up"
AUTH_REFRESH_PATH_URL = "/auth/refresh"

# Public API endpoints
PING_PATH_URL = "/api/ping"
MARKET_INFO_PATH_URL = "/api/market"
INSTRUMENTS_PATH_URL = "/api/market/instrument"
ORDER_BOOK_PATH_URL = "/api/market/{instrument}/deep"
RECENT_TRADES_PATH_URL = "/api/market/{instrument}/recent-trades"
EXTERNAL_CONTRACTS_PATH_URL = "/api/external/cmc/v1/contracts"

# Private API endpoints
USER_ME_PATH_URL = "/api/user/me"
USER_BALANCE_PATH_URL = "/api/user/balance"
USER_FUNDING_PATH_URL = "/api/user/funding"
AVAILABLE_BALANCE_PATH_URL = "/api/market/available-balance"
MARKET_POWER_PATH_URL = "/api/market/power"
DX_FEED_AUTH_PATH_URL = "/api/dx-feed/auth"

# Order endpoints
LIMIT_ORDER_PATH_URL = "/api/v2/order/limit"
MARKET_ORDER_PATH_URL = "/api/v2/order/market"
CANCEL_ORDER_PATH_URL = "/api/order/{orderId}"
GET_ORDER_PATH_URL = "/api/order/{orderId}"
GET_ORDERS_PATH_URL = "/api/order"
OPEN_ORDERS_PATH_URL = "/api/order/opened"
ORDER_FILLS_PATH_URL = "/api/fill"
MASS_CANCEL_PATH_URL = "/api/order/mass-cancel"

# Position endpoints
POSITIONS_PATH_URL = "/api/position"
POSITION_HISTORY_PATH_URL = "/api/position/history"
CLOSE_POSITION_PATH_URL = "/api/v2/position/{instrument}/close"
SET_LEVERAGE_PATH_URL = "/api/position/{instrument}"

# WebSocket endpoints
WS_HEARTBEAT_TIME_INTERVAL = 25  # Centrifugo ping interval (send before server timeout)
WS_PING_TIMEOUT = 10  # How long to wait for pong response

# Side
SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

# Time in force
TIME_IN_FORCE_GTC = "GTC"
TIME_IN_FORCE_IOC = "IOC"
TIME_IN_FORCE_FOK = "FOK"
TIME_IN_FORCE_DAY = "DAY"

# Order Types
ORDER_TYPE_LIMIT = "LIMIT"
ORDER_TYPE_MARKET = "MARKET"
ORDER_TYPE_STOP = "STOP"
ORDER_TYPE_STOP_LIMIT = "STOP_LIMIT"

# Order States
ORDER_STATE = {
    "INTENTION": OrderState.PENDING_CREATE,
    "NEW": OrderState.OPEN,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "FILLED": OrderState.FILLED,
    "CANCELLED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.CANCELED,
    "REPLACED": OrderState.OPEN,
    "ERROR": OrderState.FAILED,
}

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS = "ORDERS"

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 1200

# WebSocket event types
DIFF_STREAM_ID = 1
TRADE_STREAM_ID = 2
FUNDING_INFO_STREAM_ID = 3
HEARTBEAT_TIME_INTERVAL = 30.0

RATE_LIMITS = [
    # Pool Limits
    RateLimit(limit_id=REQUEST_WEIGHT, limit=1200, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS, limit=300, time_interval=10 * ONE_SECOND),
    # Weight Limits for individual endpoints
    RateLimit(limit_id=PING_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=MARKET_INFO_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=INSTRUMENTS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=10)]),
    RateLimit(limit_id=ORDER_BOOK_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=RECENT_TRADES_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=USER_ME_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=USER_BALANCE_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=AVAILABLE_BALANCE_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=DX_FEED_AUTH_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=LIMIT_ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1),
                             LinkedLimitWeightPair(ORDERS, weight=1)]),
    RateLimit(limit_id=MARKET_ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1),
                             LinkedLimitWeightPair(ORDERS, weight=1)]),
    RateLimit(limit_id=CANCEL_ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=GET_ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=GET_ORDERS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=OPEN_ORDERS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=ORDER_FILLS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=POSITIONS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=CLOSE_POSITION_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1),
                             LinkedLimitWeightPair(ORDERS, weight=1)]),
    RateLimit(limit_id=SET_LEVERAGE_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=EXTERNAL_CONTRACTS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=10)]),
]

ORDER_NOT_EXIST_ERROR_CODE = "ORDER_NOT_FOUND"
ORDER_NOT_EXIST_MESSAGE = "Order does not exist"

# Error messages from the exchange for detection
INSUFFICIENT_FUNDS_ERROR = "Insufficient funds"
TOO_MANY_QUANTITY_ERROR = "Too many quantity"
UNKNOWN_POSITION_ERROR = "Unknown position"
