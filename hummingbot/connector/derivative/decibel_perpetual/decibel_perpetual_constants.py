from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "decibel_perpetual"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = None

MARKET_ORDER_SLIPPAGE = 0.05

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "decibel_perpetual_testnet"

# REST API
PERPETUAL_BASE_URL = "https://api.mainnet.aptoslabs.com/decibel"
TESTNET_BASE_URL = "https://api.testnet.aptoslabs.com/decibel"

# WebSocket
PERPETUAL_WS_URL = "wss://ws.mainnet.aptoslabs.com/decibel"
TESTNET_WS_URL = "wss://ws.testnet.aptoslabs.com/decibel"

# Aptos node URLs for on-chain transactions
APTOS_MAINNET_NODE = "https://api.mainnet.aptoslabs.com/v1"
APTOS_TESTNET_NODE = "https://api.testnet.aptoslabs.com/v1"

# Decibel package address on Aptos (placeholder - must be configured)
DECIBEL_PACKAGE_ADDRESS = "0x1"  # Will be overridden by actual package address

# Price/size decimal precision
DECIMAL_PLACES = 9
DECIMAL_MULTIPLIER = 10 ** DECIMAL_PLACES

FUNDING_RATE_UPDATE_INTERNAL_SECOND = 60

CURRENCY = "USD"

# REST endpoints
MARKETS_URL = "/api/v1/markets"
DEPTH_URL = "/api/v1/depth"
PRICES_URL = "/api/v1/prices"
ASSET_CONTEXTS_URL = "/api/v1/asset_contexts"
CANDLESTICKS_URL = "/api/v1/candlesticks"
TRADES_URL = "/api/v1/trades"
ACCOUNT_POSITIONS_URL = "/api/v1/account_positions"
OPEN_ORDERS_URL = "/api/v1/open_orders"
ORDERS_URL = "/api/v1/orders"
ACCOUNT_OVERVIEWS_URL = "/api/v1/account_overviews"
ORDER_HISTORY_URL = "/api/v1/order_history"
TRADE_HISTORY_URL = "/api/v1/trade_history"
FUNDING_RATE_HISTORY_URL = "/api/v1/funding_rate_history"

PING_URL = MARKETS_URL  # Use markets endpoint as health check

# WebSocket topics
WS_DEPTH_TOPIC = "depth"
WS_PRICES_TOPIC = "prices"
WS_TRADES_TOPIC = "trades"
WS_MARKET_PRICE_TOPIC = "market_price"
WS_ACCOUNT_OPEN_ORDERS_TOPIC = "account_open_orders"
WS_ACCOUNT_POSITIONS_TOPIC = "account_positions"
WS_ORDER_UPDATE_TOPIC = "order_update"
WS_ACCOUNT_OVERVIEW_TOPIC = "account_overview"

# On-chain entry functions
PLACE_ORDER_FUNCTION = "dex_accounts_entry::place_order_to_subaccount"
CANCEL_ORDER_FUNCTION = "dex_accounts_entry::cancel_order"

# Order States
ORDER_STATE = {
    "open": OrderState.OPEN,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "filled": OrderState.FILLED,
    "canceled": OrderState.CANCELED,
    "cancelled": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
    "expired": OrderState.CANCELED,
}

HEARTBEAT_TIME_INTERVAL = 30.0

MAX_REQUEST = 600
ALL_ENDPOINTS_LIMIT = "All"

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=MAX_REQUEST, time_interval=60),
    RateLimit(limit_id=MARKETS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=DEPTH_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=PRICES_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ASSET_CONTEXTS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ACCOUNT_POSITIONS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=OPEN_ORDERS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ORDERS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ACCOUNT_OVERVIEWS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ORDER_HISTORY_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=TRADE_HISTORY_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=FUNDING_RATE_HISTORY_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=TRADES_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=PING_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
]

ORDER_NOT_EXIST_MESSAGE = "order not found"
UNKNOWN_ORDER_MESSAGE = "Order was never placed, already canceled, or filled"
