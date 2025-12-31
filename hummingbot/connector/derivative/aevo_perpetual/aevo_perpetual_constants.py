from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "aevo_perpetual"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = 36

MARKET_ORDER_SLIPPAGE = 0.05

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "aevo_perpetual_testnet"

# REST API URLs
PERPETUAL_BASE_URL = "https://api.aevo.xyz"
TESTNET_BASE_URL = "https://api-testnet.aevo.xyz"

# WebSocket URLs
PERPETUAL_WS_URL = "wss://ws.aevo.xyz"
TESTNET_WS_URL = "wss://ws-testnet.aevo.xyz"

# EIP-712 Domain Configuration
MAINNET_DOMAIN_NAME = "Aevo Mainnet"
TESTNET_DOMAIN_NAME = "Aevo Testnet"
DOMAIN_VERSION = "1"
MAINNET_CHAIN_ID = 1
TESTNET_CHAIN_ID = 11155111

FUNDING_RATE_UPDATE_INTERVAL_SECOND = 3600  # 1 hour funding intervals

CURRENCY = "USDC"

# REST API Endpoints
ACCOUNT_INFO_URL = "/account"
PORTFOLIO_URL = "/portfolio"
POSITIONS_URL = "/positions"
ORDERS_URL = "/orders"
ORDER_URL = "/orders/{order_id}"
ORDERS_ALL_URL = "/orders-all"
ORDERBOOK_URL = "/orderbook"
MARKETS_URL = "/markets"
INSTRUMENT_URL = "/instrument/{instrument_name}"
FUNDING_URL = "/funding"
TRADES_URL = "/trades"
TICKER_URL = "/ticker"
INDEX_URL = "/index"
STATISTICS_URL = "/statistics"
TIME_URL = "/time"

# WebSocket Channels
WS_ORDERBOOK_CHANNEL = "orderbook"
WS_TRADES_CHANNEL = "trades"
WS_TICKER_CHANNEL = "ticker"
WS_INDEX_CHANNEL = "index"
WS_ORDERS_CHANNEL = "orders"
WS_FILLS_CHANNEL = "fills"
WS_POSITIONS_CHANNEL = "positions"

# Order States
ORDER_STATE = {
    "open": OrderState.OPEN,
    "pending": OrderState.PENDING_CREATE,
    "filled": OrderState.FILLED,
    "partial": OrderState.PARTIALLY_FILLED,
    "cancelled": OrderState.CANCELED,
    "expired": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
}

HEARTBEAT_TIME_INTERVAL = 30.0

# Rate Limits (requests per minute)
MAX_REQUEST = 300
ALL_ENDPOINTS_LIMIT = "All"

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=MAX_REQUEST, time_interval=60),
    RateLimit(limit_id=ACCOUNT_INFO_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=PORTFOLIO_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=POSITIONS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ORDERS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ORDERBOOK_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=MARKETS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=FUNDING_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=TRADES_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=TIME_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
]

ORDER_NOT_EXIST_MESSAGE = "order not found"
UNKNOWN_ORDER_MESSAGE = "Order does not exist"
