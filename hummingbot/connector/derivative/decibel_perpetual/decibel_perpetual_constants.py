from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "decibel_perpetual"
BROKER_ID = "HBOT"

DEFAULT_DOMAIN = "decibel_perpetual"
TESTNET_DOMAIN = "decibel_perpetual_testnet"

# Base URLs
MAINNET_BASE_URL = "https://api.mainnet.aptoslabs.com/decibel"
TESTNET_BASE_URL = "https://api.testnet.aptoslabs.com/decibel"

# Aptos fullnode URLs
MAINNET_FULLNODE_URL = "https://fullnode.mainnet.aptoslabs.com/v1"
TESTNET_FULLNODE_URL = "https://fullnode.testnet.aptoslabs.com/v1"

# Smart contract package addresses
MAINNET_PACKAGE = "0x8304621d9c0f6f20b3b5d1bcf44def4ac5c8bf7c986c56c73eebb0a3ba4dce91"
TESTNET_PACKAGE = "0x1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b"

# REST API paths
GET_MARKETS_PATH_URL = "/api/v1/markets"
GET_MARKET_PRICES_PATH_URL = "/api/v1/prices"
GET_RECENT_TRADES_PATH_URL = "/api/v1/trades"
GET_ACCOUNT_OVERVIEW_PATH_URL = "/api/v1/account_overviews"
GET_ACCOUNT_POSITIONS_PATH_URL = "/api/v1/account_positions"
GET_ACCOUNT_OPEN_ORDERS_PATH_URL = "/api/v1/open_orders"
GET_USER_ORDER_HISTORY_PATH_URL = "/api/v1/order_history"
GET_USER_TRADE_HISTORY_PATH_URL = "/api/v1/trades"
GET_USER_FUNDING_HISTORY_PATH_URL = "/api/v1/funding_rate_history"
GET_BULK_ORDER_STATUS_PATH_URL = "/api/v1/bulk_order_status"

# Order state mappings from Decibel to Hummingbot
ORDER_STATE = {
    "Open": OrderState.OPEN,
    "Pending": OrderState.PENDING_CREATE,
    "Filled": OrderState.FILLED,
    "PartiallyFilled": OrderState.PARTIALLY_FILLED,
    "Cancelled": OrderState.CANCELED,
    "Rejected": OrderState.FAILED,
    "Expired": OrderState.CANCELED,
    "OPEN": OrderState.OPEN,
    "PENDING": OrderState.PENDING_CREATE,
    "FILLED": OrderState.FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "CANCELLED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.CANCELED,
}

# Fee rates (Decibel fixed fees)
MAKER_FEE_RATE = 0.00015   # 0.015%
TAKER_FEE_RATE = 0.00040   # 0.040%

# Polling intervals (seconds)
POLL_INTERVAL = 10.0
HEARTBEAT_TIME_INTERVAL = 30.0

# Rate limits
MAX_REQUEST = 200
ALL_ENDPOINTS_LIMIT = "All"

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=MAX_REQUEST, time_interval=30),
    RateLimit(
        limit_id=GET_MARKETS_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=30,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=GET_MARKET_PRICES_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=30,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=GET_RECENT_TRADES_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=30,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=GET_ACCOUNT_OVERVIEW_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=30,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=GET_ACCOUNT_POSITIONS_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=30,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=GET_ACCOUNT_OPEN_ORDERS_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=30,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=GET_USER_ORDER_HISTORY_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=30,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=GET_USER_TRADE_HISTORY_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=30,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=GET_USER_FUNDING_HISTORY_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=30,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=GET_BULK_ORDER_STATUS_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=30,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
]

ORDER_NOT_EXIST_ERROR_CODE = "ORDER_NOT_FOUND"
ORDER_NOT_EXIST_MESSAGE = "order not found"
UNKNOWN_ORDER_MESSAGE = "Order was never placed, already canceled, or filled"
