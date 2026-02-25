"""Backpack exchange constants."""
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "com"

# Order ID configuration
HBOT_ORDER_ID_PREFIX = "x-HBOT"
MAX_ORDER_ID_LEN = 32

# Base URLs
REST_URL = "https://api.backpack.exchange"
WSS_URL = "wss://ws.backpack.exchange"

# API Versions
PUBLIC_API_VERSION = "v1"
PRIVATE_API_VERSION = "v1"

# Public API endpoints
PING_PATH_URL = "/api/v1/ping"
TIME_PATH_URL = "/api/v1/time"
MARKETS_PATH_URL = "/api/v1/markets"
TICKER_PATH_URL = "/api/v1/ticker"
TICKERS_PATH_URL = "/api/v1/tickers"
DEPTH_PATH_URL = "/api/v1/depth"
TRADES_PATH_URL = "/api/v1/trades"
KLINES_PATH_URL = "/api/v1/klines"

# Private API endpoints
ACCOUNT_PATH_URL = "/api/v1/account"
CAPITAL_PATH_URL = "/api/v1/capital"
ORDER_PATH_URL = "/api/v1/order"
ORDERS_PATH_URL = "/api/v1/orders"
FILLS_PATH_URL = "/api/v1/fills"
POSITIONS_PATH_URL = "/api/v1/positions"

# WebSocket endpoints
WS_PUBLIC_STREAM = "/ws"
WS_PRIVATE_STREAM = "/ws"

# WebSocket heartbeat interval (seconds)
WS_HEARTBEAT_TIME_INTERVAL = 30

# Order sides
SIDE_BID = "Bid"
SIDE_ASK = "Ask"

# Order types
ORDER_TYPE_LIMIT = "Limit"
ORDER_TYPE_MARKET = "Market"

# Time in force
TIME_IN_FORCE_GTC = "GTC"  # Good till cancelled
TIME_IN_FORCE_IOC = "IOC"  # Immediate or cancel
TIME_IN_FORCE_FOK = "FOK"  # Fill or kill

# Rate Limit Types
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS = "ORDERS"
ORDERS_24HR = "ORDERS_24HR"
RAW_REQUESTS = "RAW_REQUESTS"

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

# Rate limits (based on Backpack documentation)
MAX_REQUEST_WEIGHT_PER_MINUTE = 6000
MAX_ORDERS_PER_10_SECONDS = 100
MAX_ORDERS_PER_24HR = 200000
MAX_RAW_REQUESTS_PER_5_MINUTES = 61000

# Order States mapping
ORDER_STATE = {
    "New": OrderState.OPEN,
    "Filled": OrderState.FILLED,
    "PartiallyFilled": OrderState.PARTIALLY_FILLED,
    "Cancelled": OrderState.CANCELED,
    "Expired": OrderState.FAILED,
    "Rejected": OrderState.FAILED,
}

# WebSocket event types
WS_TRADE_EVENT = "trade"
WS_ORDER_BOOK_EVENT = "depth"
WS_TICKER_EVENT = "ticker"
WS_ORDER_UPDATE_EVENT = "orderUpdate"
WS_BALANCE_UPDATE_EVENT = "balanceUpdate"
WS_POSITION_UPDATE_EVENT = "positionUpdate"

# Rate Limits configuration
RATE_LIMITS = [
    # Pools
    RateLimit(limit_id=REQUEST_WEIGHT, limit=MAX_REQUEST_WEIGHT_PER_MINUTE, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS, limit=MAX_ORDERS_PER_10_SECONDS, time_interval=10 * ONE_SECOND),
    RateLimit(limit_id=ORDERS_24HR, limit=MAX_ORDERS_PER_24HR, time_interval=ONE_DAY),
    RateLimit(limit_id=RAW_REQUESTS, limit=MAX_RAW_REQUESTS_PER_5_MINUTES, time_interval=5 * ONE_MINUTE),
    
    # Public endpoints
    RateLimit(
        limit_id=PING_PATH_URL,
        limit=MAX_REQUEST_WEIGHT_PER_MINUTE,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1), LinkedLimitWeightPair(RAW_REQUESTS, 1)]
    ),
    RateLimit(
        limit_id=TIME_PATH_URL,
        limit=MAX_REQUEST_WEIGHT_PER_MINUTE,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1), LinkedLimitWeightPair(RAW_REQUESTS, 1)]
    ),
    RateLimit(
        limit_id=MARKETS_PATH_URL,
        limit=MAX_REQUEST_WEIGHT_PER_MINUTE,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10), LinkedLimitWeightPair(RAW_REQUESTS, 1)]
    ),
    RateLimit(
        limit_id=TICKER_PATH_URL,
        limit=MAX_REQUEST_WEIGHT_PER_MINUTE,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 2), LinkedLimitWeightPair(RAW_REQUESTS, 1)]
    ),
    RateLimit(
        limit_id=TICKERS_PATH_URL,
        limit=MAX_REQUEST_WEIGHT_PER_MINUTE,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10), LinkedLimitWeightPair(RAW_REQUESTS, 1)]
    ),
    RateLimit(
        limit_id=DEPTH_PATH_URL,
        limit=MAX_REQUEST_WEIGHT_PER_MINUTE,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 20), LinkedLimitWeightPair(RAW_REQUESTS, 1)]
    ),
    RateLimit(
        limit_id=TRADES_PATH_URL,
        limit=MAX_REQUEST_WEIGHT_PER_MINUTE,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 5), LinkedLimitWeightPair(RAW_REQUESTS, 1)]
    ),
    RateLimit(
        limit_id=KLINES_PATH_URL,
        limit=MAX_REQUEST_WEIGHT_PER_MINUTE,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 5), LinkedLimitWeightPair(RAW_REQUESTS, 1)]
    ),
    
    # Private endpoints
    RateLimit(
        limit_id=ACCOUNT_PATH_URL,
        limit=MAX_REQUEST_WEIGHT_PER_MINUTE,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 5), LinkedLimitWeightPair(RAW_REQUESTS, 1)]
    ),
    RateLimit(
        limit_id=CAPITAL_PATH_URL,
        limit=MAX_REQUEST_WEIGHT_PER_MINUTE,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10), LinkedLimitWeightPair(RAW_REQUESTS, 1)]
    ),
    RateLimit(
        limit_id=ORDER_PATH_URL,
        limit=MAX_REQUEST_WEIGHT_PER_MINUTE,
        time_interval=ONE_MINUTE,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_WEIGHT, 5),
            LinkedLimitWeightPair(ORDERS, 1),
            LinkedLimitWeightPair(ORDERS_24HR, 1),
            LinkedLimitWeightPair(RAW_REQUESTS, 1)
        ]
    ),
    RateLimit(
        limit_id=ORDERS_PATH_URL,
        limit=MAX_REQUEST_WEIGHT_PER_MINUTE,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10), LinkedLimitWeightPair(RAW_REQUESTS, 1)]
    ),
    RateLimit(
        limit_id=FILLS_PATH_URL,
        limit=MAX_REQUEST_WEIGHT_PER_MINUTE,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10), LinkedLimitWeightPair(RAW_REQUESTS, 1)]
    ),
    RateLimit(
        limit_id=POSITIONS_PATH_URL,
        limit=MAX_REQUEST_WEIGHT_PER_MINUTE,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10), LinkedLimitWeightPair(RAW_REQUESTS, 1)]
    ),
]

# Error codes
ORDER_NOT_FOUND_ERROR_CODE = "ORDER_NOT_FOUND"
ORDER_NOT_FOUND_MESSAGE = "Order not found"
INSUFFICIENT_BALANCE_ERROR = "INSUFFICIENT_BALANCE"
RATE_LIMIT_ERROR = "RATE_LIMIT_EXCEEDED"

# Market types
MARKET_TYPE_SPOT = "SPOT"
MARKET_TYPE_PERP = "PERP"
MARKET_TYPE_IPERP = "IPERP"
MARKET_TYPE_DATED = "DATED"
MARKET_TYPE_PREDICTION = "PREDICTION"
MARKET_TYPE_RFQ = "RFQ"

# Kline intervals
KLINES_INTERVALS = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1month"]
