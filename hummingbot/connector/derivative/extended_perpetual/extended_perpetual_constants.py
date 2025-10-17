# A single source of truth for constant variables related to Extended Perpetual
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "extended_perpetual"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = 32

MARKET_ORDER_SLIPPAGE = 0.05

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "extended_perpetual_testnet"

# Extended Perpetual API endpoints - Starknet mainnet
BASE_URL = "https://api.starknet.extended.exchange"
TESTNET_BASE_URL = "https://api.starknet.sepolia.extended.exchange"
# WebSocket base URLs (specific paths are appended when connecting)
WS_URL = "wss://api.starknet.extended.exchange"
TESTNET_WS_URL = "wss://api.starknet.sepolia.extended.exchange"

FUNDING_RATE_UPDATE_INTERNAL_SECOND = 60
CURRENCY = "USDC"

# API Endpoints - Extended API v1
# Public endpoints
# NOTE: Extended uses /info/markets/ for ALL endpoints (both listing and individual market data)
EXCHANGE_INFO_URL = "/api/v1/info/markets"  # List all markets
PING_URL = "/api/v1/info/markets"  # Ping endpoint
TICKER_PRICE_CHANGE_URL = "/api/v1/info/markets/stats"  # Individual market stats (with {market} in path)
SNAPSHOT_REST_URL = "/api/v1/info/markets/orderbook"  # Individual market orderbook (with {market} in path)
FUNDING_RATES_URL = "/api/v1/info/markets/funding-rates"  # Individual market funding (with {market} in path)
MARK_PRICE_URL = "/api/v1/info/markets/stats"  # Individual market mark price (with {market} in path)

# Private endpoints
ACCOUNT_INFO_URL = "/api/v1/user/account"
BALANCE_URL = "/api/v1/user/balance"
POSITIONS_URL = "/api/v1/user/positions"
LEVERAGE_URL = "/api/v1/user/leverage"

# Order endpoints
CANCEL_ORDER_URL = "/api/v1/user/orders"
CREATE_ORDER_URL = "/api/v1/user/orders"
ORDER_URL = "/api/v1/user/orders"
OPEN_ORDERS_URL = "/api/v1/user/orders"
ACCOUNT_TRADE_LIST_URL = "/api/v1/user/trades"
MY_TRADES_PATH_URL = "/api/v1/user/trades"
FUNDING_PAYMENTS_URL = "/api/v1/user/funding-payments"

# WebSocket channels
TRADES_ENDPOINT_NAME = "trades"
DEPTH_ENDPOINT_NAME = "orderbook"
USER_ORDERS_ENDPOINT_NAME = "account-updates"
USEREVENT_ENDPOINT_NAME = "account-updates"
MARK_PRICE_CHANNEL = "mark-price"
FUNDING_RATE_CHANNEL = "funding-rates"

DIFF_EVENT_TYPE = "orderbook"
TRADE_EVENT_TYPE = "trades"

# Order Statuses - Extended format
ORDER_STATE = {
    "pending": OrderState.PENDING_CREATE,
    "open": OrderState.OPEN,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "filled": OrderState.FILLED,
    "cancelled": OrderState.CANCELED,
    "canceled": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
    "expired": OrderState.CANCELED,
}

HEARTBEAT_TIME_INTERVAL = 30.0

MAX_REQUEST = 1_200
ALL_ENDPOINTS_LIMIT = "All"

RATE_LIMITS = [
    RateLimit(limit_id=ALL_ENDPOINTS_LIMIT, limit=100, time_interval=1),
    
    # Public endpoints
    RateLimit(
        limit_id=EXCHANGE_INFO_URL,
        limit=100,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=TICKER_PRICE_CHANGE_URL,
        limit=100,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=SNAPSHOT_REST_URL,
        limit=100,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=FUNDING_RATES_URL,
        limit=100,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    
    # Private endpoints
    RateLimit(
        limit_id=ACCOUNT_INFO_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=BALANCE_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=POSITIONS_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=CREATE_ORDER_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=CANCEL_ORDER_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=MY_TRADES_PATH_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
]

