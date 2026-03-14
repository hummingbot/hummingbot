from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "evedex_perpetual"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = None
MIN_NOTIONAL_SIZE = 5.0  # EVEDEX minVolume is $5

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "evedex_perpetual_testnet"

# Production API
TRADE_BASE_URL = "https://trading-api.evedex.com"
AUTH_BASE_URL = "https://auth-api.evedex.com"
WS_URL = "wss://ws.evedex.com/connection/websocket"
WS_CHANNEL_PREFIX = "futures-perp"
CHAIN_ID = 161803

# Testnet / Demo API
TESTNET_TRADE_BASE_URL = "https://trading-api.evedex.io"
TESTNET_AUTH_BASE_URL = "https://auth-api.evedex.io"
TESTNET_WS_URL = "wss://ws.evedex.io/connection/websocket"
TESTNET_WS_CHANNEL_PREFIX = "futures-perp-beta"
TESTNET_CHAIN_ID = 16182

# REST endpoints
INSTRUMENTS_URL = "/api/market/instrument"
MARKET_INFO_URL = "/api/market"
ORDER_BOOK_URL = "/api/market/{instrument}/deep"
RECENT_TRADES_URL = "/api/market/{instrument}/recent-trades"
FUNDING_RATE_URL = "/api/market/instrument"   # funding rate in instrument metrics

# Auth endpoints
AUTH_NONCE_URL = "/auth/nonce"
AUTH_SIGNIN_URL = "/auth/user/sign-up"
AUTH_ME_URL = "/auth/user/me"

# Private REST endpoints
USER_BALANCE_URL = "/api/user/balance"
USER_FUNDING_URL = "/api/user/funding"
POSITIONS_URL = "/api/position"
OPEN_ORDERS_URL = "/api/order/opened"
ORDER_URL = "/api/order/{order_id}"
CREATE_LIMIT_ORDER_URL = "/api/v2/order/limit"
CREATE_MARKET_ORDER_URL = "/api/v2/order/market"
CANCEL_ORDER_URL = "/api/order/{order_id}"
MASS_CANCEL_URL = "/api/order/mass-cancel"

# WebSocket channel templates (Centrifuge protocol)
# Market channels
WS_ORDERBOOK_CHANNEL = "orderBook-{instrument}-0.1"
WS_ORDERBOOK_BEST_CHANNEL = "orderBook-{instrument}-best"
WS_TRADES_CHANNEL = "trade-{instrument}"
WS_RECENT_TRADES_CHANNEL = "recent-trade-{instrument}"
WS_FUNDING_RATE_CHANNEL = "funding-rate"
WS_INSTRUMENTS_CHANNEL = "instruments"
WS_HEARTBEAT_CHANNEL = "heartbeat"

# User channels (require auth)
WS_USER_ACCOUNT_CHANNEL = "user-{user_id}"
WS_USER_ORDERS_CHANNEL = "order-{user_id}"
WS_USER_POSITIONS_CHANNEL = "position-{user_id}"
WS_USER_FILLS_CHANNEL = "orderFills-{user_id}"
WS_USER_FUNDING_CHANNEL = "funding-{user_id}"

HEARTBEAT_TIME_INTERVAL = 30.0
FUNDING_RATE_UPDATE_INTERNAL_SECOND = 60

# Order states
ORDER_STATE = {
    "ACTIVE": OrderState.OPEN,
    "PENDING": OrderState.OPEN,
    "OPENED": OrderState.OPEN,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "FILLED": OrderState.FILLED,
    "CANCELED": OrderState.CANCELED,
    "CANCELLED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.CANCELED,
}

MAX_REQUEST = 300
ALL_ENDPOINTS_LIMIT = "All"

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=MAX_REQUEST, time_interval=60),
    RateLimit(limit_id=INSTRUMENTS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=CREATE_LIMIT_ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=CREATE_MARKET_ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=OPEN_ORDERS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=POSITIONS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=USER_BALANCE_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=MASS_CANCEL_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
]

ORDER_NOT_EXIST_MESSAGE = "order not found"
UNKNOWN_ORDER_MESSAGE = "Order was never placed, already canceled, or filled"

# EIP-712 domain for order signing
EIP712_DOMAIN_NAME = "evedex"
EIP712_DOMAIN_VERSION = "1"
