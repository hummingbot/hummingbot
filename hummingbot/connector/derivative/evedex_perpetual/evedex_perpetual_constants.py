from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "evedex_perpetual"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = None

MARKET_ORDER_SLIPPAGE = 0.05

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "evedex_perpetual_testnet"

# EVEDEX API endpoints
# Production environment
PERPETUAL_BASE_URL = "https://api.evedex.com"
PERPETUAL_WS_URL = "wss://centrifuge.evedex.com/connection/websocket"

# Demo/Testnet environment
TESTNET_BASE_URL = "https://api.demo-exchange.evedex.com"
TESTNET_WS_URL = "wss://centrifuge.demo-exchange.evedex.com/connection/websocket"

# Auth service URLs
AUTH_BASE_URL = "https://auth.evedex.com"
TESTNET_AUTH_BASE_URL = "https://auth.demo-exchange.evedex.com"

FUNDING_RATE_UPDATE_INTERNAL_SECOND = 60

CURRENCY = "USDT"

# REST API Endpoints
EXCHANGE_INFO_URL = "/api/v1/public/instruments"
MARKET_DEPTH_URL = "/api/v1/public/orderbook"
TICKER_PRICE_URL = "/api/v1/public/ticker"
TRADES_URL = "/api/v1/public/trades"
KLINES_URL = "/api/v1/public/klines"

# Private endpoints
CREATE_ORDER_URL = "/api/v1/private/order"
CANCEL_ORDER_URL = "/api/v1/private/order"
ORDER_STATUS_URL = "/api/v1/private/order"
OPEN_ORDERS_URL = "/api/v1/private/orders"
USER_TRADES_URL = "/api/v1/private/trades"
ACCOUNT_INFO_URL = "/api/v1/private/account"
BALANCE_URL = "/api/v1/private/balance"
POSITIONS_URL = "/api/v1/private/positions"
SET_LEVERAGE_URL = "/api/v1/private/leverage"
FUNDING_RATE_URL = "/api/v1/public/funding-rate"

PING_URL = "/api/v1/public/time"

# WebSocket subscription types
WS_ORDERBOOK_CHANNEL = "orderbook"
WS_TRADES_CHANNEL = "trades"
WS_TICKER_CHANNEL = "ticker"
WS_USER_ORDERS_CHANNEL = "orders"
WS_USER_TRADES_CHANNEL = "user_trades"
WS_USER_POSITIONS_CHANNEL = "positions"
WS_USER_BALANCE_CHANNEL = "balance"

# Order Statuses mapping
ORDER_STATE = {
    "new": OrderState.OPEN,
    "open": OrderState.OPEN,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "filled": OrderState.FILLED,
    "canceled": OrderState.CANCELED,
    "cancelled": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
    "expired": OrderState.CANCELED,
    "pending_cancel": OrderState.PENDING_CANCEL,
}

HEARTBEAT_TIME_INTERVAL = 30.0

# Rate limits - EVEDEX allows 30 heavy requests per 60 seconds
MAX_REQUEST = 30
ALL_ENDPOINTS_LIMIT = "All"
HEAVY_ENDPOINTS_LIMIT = "Heavy"

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=1200, time_interval=60),
    RateLimit(HEAVY_ENDPOINTS_LIMIT, limit=MAX_REQUEST, time_interval=60),

    # Public endpoints (light weight)
    RateLimit(limit_id=EXCHANGE_INFO_URL, limit=1200, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=MARKET_DEPTH_URL, limit=1200, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=TICKER_PRICE_URL, limit=1200, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=TRADES_URL, limit=1200, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=PING_URL, limit=1200, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=FUNDING_RATE_URL, limit=1200, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),

    # Private endpoints (heavy weight)
    RateLimit(limit_id=CREATE_ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT), LinkedLimitWeightPair(HEAVY_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=CANCEL_ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT), LinkedLimitWeightPair(HEAVY_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ORDER_STATUS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT), LinkedLimitWeightPair(HEAVY_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=OPEN_ORDERS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT), LinkedLimitWeightPair(HEAVY_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=USER_TRADES_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT), LinkedLimitWeightPair(HEAVY_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ACCOUNT_INFO_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT), LinkedLimitWeightPair(HEAVY_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=BALANCE_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT), LinkedLimitWeightPair(HEAVY_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=POSITIONS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT), LinkedLimitWeightPair(HEAVY_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=SET_LEVERAGE_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT), LinkedLimitWeightPair(HEAVY_ENDPOINTS_LIMIT)]),
]

ORDER_NOT_EXIST_MESSAGE = "order not found"
UNKNOWN_ORDER_MESSAGE = "Order does not exist"

# Order constraints
MAX_ACTIVE_ORDERS = 500
MAX_ACTIVE_TP_SL_ORDERS = 500
MIN_ORDER_NOTIONAL_USD = 5
