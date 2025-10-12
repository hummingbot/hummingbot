import sys

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import OrderState

# Connector constants
CLIENT_ID_PREFIX = "HBOT"
MAX_ID_LEN = 32
SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 30 * 0.8

# Base URLs
DEFAULT_DOMAIN = "evedex_main"
REST_URL = "https://exchange-api.evedex.com"

# REST API Public Endpoints
SERVER_TIME_PATH = "/api/ping"
MARKET_INFO_PATH = "/api/market"
INSTRUMENTS_PATH = "/api/market/instrument"
ORDER_BOOK_PATH_TEMPLATE = "/api/market/{instrument}/deep"
RECENT_TRADES_PATH_TEMPLATE = "/api/market/{instrument}/recent-trades"

# REST API Private Endpoints (Auth required)
BALANCE_PATH = "/api/user/balance"
ORDER_LIMIT_V2_PATH = "/api/v2/order/limit"
ORDER_MARKET_V2_PATH = "/api/v2/order/market"
ORDER_STATUS_PATH_TEMPLATE = "/api/order/{orderId}"
ORDER_FILLS_PATH_TEMPLATE = "/api/order/{orderId}/fill"
ORDERS_PATH = "/api/order"

# Rate limiting identifiers
PUBLIC_REQUEST_LIMIT_ID = "PublicREST"
PRIVATE_REQUEST_LIMIT_ID = "PrivateREST"

# Order States Mapping
ORDER_STATE = {
    "NEW": OrderState.OPEN,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "FILLED": OrderState.FILLED,
    "CANCELED": OrderState.CANCELED,
    "PENDING_CANCEL": OrderState.PENDING_CANCEL,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.CANCELED,
}

# Order Types Mapping
ORDER_TYPE_MAP = {
    OrderType.LIMIT: "LIMIT",
    OrderType.MARKET: "MARKET",
    OrderType.LIMIT_MAKER: "LIMIT_MAKER",
}

# Side Mapping
SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

# Time in Force
TIME_IN_FORCE_GTC = "GTC"  # Good Till Cancel
TIME_IN_FORCE_IOC = "IOC"  # Immediate or Cancel
TIME_IN_FORCE_FOK = "FOK"  # Fill or Kill

NO_LIMIT = sys.maxsize

# Rate Limiting
RATE_LIMITS = [
    RateLimit(limit_id=PUBLIC_REQUEST_LIMIT_ID, limit=10, time_interval=1),
    RateLimit(limit_id=PRIVATE_REQUEST_LIMIT_ID, limit=5, time_interval=1),
    RateLimit(limit_id=SERVER_TIME_PATH, limit=5, time_interval=1),
    RateLimit(limit_id=INSTRUMENTS_PATH, limit=10, time_interval=1),
    RateLimit(limit_id=MARKET_INFO_PATH, limit=5, time_interval=1),
    RateLimit(limit_id=BALANCE_PATH, limit=5, time_interval=1),
    RateLimit(limit_id=ORDER_LIMIT_V2_PATH, limit=5, time_interval=1),
    RateLimit(limit_id=ORDER_MARKET_V2_PATH, limit=5, time_interval=1),
    RateLimit(limit_id=ORDERS_PATH, limit=5, time_interval=1),
]
