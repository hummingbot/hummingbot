from decimal import Decimal

from decibel import MAINNET_CONFIG, NETNA_CONFIG, TESTNET_CONFIG

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "decibel_perpetual"
DEFAULT_DOMAIN = EXCHANGE_NAME

# Transaction timeout configuration (seconds)
DEFAULT_PLACE_ORDER_TIMEOUT_SECS = 120.0
DEFAULT_CANCEL_ORDER_TIMEOUT_SECS = 120.0

# Base URLs - Mainnet
REST_URL = "https://api.mainnet.aptoslabs.com/decibel"
WSS_URL = "wss://api.mainnet.aptoslabs.com/decibel/ws"
FULLNODE_URL = "https://api.mainnet.aptoslabs.com/v1"

# Netna (Staging)
NETNA_DOMAIN = "decibel_perpetual_netna"
NETNA_REST_URL = "https://api.netna.staging.aptoslabs.com/decibel"
NETNA_WSS_URL = "wss://api.netna.staging.aptoslabs.com/decibel/ws"
NETNA_FULLNODE_URL = "https://api.netna.staging.aptoslabs.com/v1"

# Testnet
TESTNET_DOMAIN = "decibel_perpetual_testnet"
TESTNET_REST_URL = "https://api.testnet.aptoslabs.com/decibel"
TESTNET_WSS_URL = "wss://api.testnet.aptoslabs.com/decibel/ws"
TESTNET_FULLNODE_URL = "https://api.testnet.aptoslabs.com/v1"

# Aptos deployment addresses
MAINNET_PACKAGE = MAINNET_CONFIG.deployment.package
NETNA_PACKAGE = NETNA_CONFIG.deployment.package
TESTNET_PACKAGE = TESTNET_CONFIG.deployment.package

# Order state mapping
ORDER_STATE = {
    "Open": OrderState.OPEN,
    "Filled": OrderState.FILLED,
    "PartiallyFilled": OrderState.PARTIALLY_FILLED,
    "Cancelled": OrderState.CANCELED,
    "Rejected": OrderState.FAILED,
    "Expired": OrderState.CANCELED,
}

# REST API Endpoints
# Note: Decibel does NOT expose a REST orderbook/depth endpoint.
GET_MARKETS_PATH_URL = "/api/v1/markets"
GET_MARKET_PRICES_PATH_URL = "/api/v1/prices"
GET_ACCOUNT_OVERVIEW_PATH_URL = "/api/v1/account_overviews"
GET_ACCOUNT_POSITIONS_PATH_URL = "/api/v1/account_positions"
GET_ORDER_PATH_URL = "/api/v1/orders"
GET_USER_TRADE_HISTORY_PATH_URL = "/api/v1/trade_history"
GET_USER_FUNDING_HISTORY_PATH_URL = "/api/v1/funding_rate_history"

# WebSocket Channels
# Public channels - topics use market addresses, not market names
WS_MARKET_PRICE_CHANNEL = "market_price"
WS_MARKET_DEPTH_CHANNEL = "depth"
WS_MARKET_TRADES_CHANNEL = "trades"

# Private channels (require subaccount address)
WS_ACCOUNT_OVERVIEW_CHANNEL = "account_overview"
WS_USER_POSITIONS_CHANNEL = "user_positions"
WS_USER_OPEN_ORDERS_CHANNEL = "account_open_orders"
WS_USER_TRADES_CHANNEL = "user_trades"
WS_ORDER_UPDATE_CHANNEL = "order_update"

# WebSocket configuration
WS_PING_INTERVAL = 30  # seconds

# Rate Limits
DECIBEL_LIMIT_ID = "DECIBEL_LIMIT"
DECIBEL_API_LIMIT = 400  # requests per minute
DECIBEL_LIMIT_INTERVAL = 60  # seconds

# Endpoint costs (weight per request type)
STANDARD_REQUEST_COST = 1
HEAVY_REQUEST_COST = 10

# Market order slippage (IOC orders simulate market orders)
MARKET_ORDER_SLIPPAGE = Decimal("0.08")  # 8%

# Fee tier schedule (source: https://docs.decibel.trade/for-traders/fees).
# Decibel has no public endpoint to query a user's tier directly; the Decibel
# team confirmed the tiers are computed off the 30-day trading volume returned
# by /api/v1/account_overviews when queried with volume_window="30d".
# Entries are sorted DESCENDING by min 30-day volume so the highest qualifying
# tier matches first when iterating.
VOLUME_WINDOW_30D = "30d"
FEE_TIER_SCHEDULE = [
    # (tier, min_30d_volume_usd, maker_decimal, taker_decimal)
    (6, Decimal("15000000000"), Decimal("0"), Decimal("0.00018")),      # > $15B
    (5, Decimal("4000000000"), Decimal("0"), Decimal("0.00019")),       # > $4B
    (4, Decimal("1000000000"), Decimal("0"), Decimal("0.00021")),       # > $1B
    (3, Decimal("200000000"), Decimal("0.00003"), Decimal("0.00022")),  # > $200M
    (2, Decimal("50000000"), Decimal("0.00006"), Decimal("0.00025")),   # > $50M
    (1, Decimal("10000000"), Decimal("0.00009"), Decimal("0.0003")),    # > $10M
    (0, Decimal("0"), Decimal("0.00011"), Decimal("0.00034")),          # Tier 0 (default)
]

# Single rate limit tier (API key required for all requests)
RATE_LIMITS = [
    RateLimit(limit_id=DECIBEL_LIMIT_ID, limit=DECIBEL_API_LIMIT, time_interval=DECIBEL_LIMIT_INTERVAL),
    RateLimit(limit_id=GET_MARKETS_PATH_URL, limit=DECIBEL_API_LIMIT, time_interval=DECIBEL_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=DECIBEL_LIMIT_ID, weight=STANDARD_REQUEST_COST)]),
    RateLimit(limit_id=GET_MARKET_PRICES_PATH_URL, limit=DECIBEL_API_LIMIT, time_interval=DECIBEL_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=DECIBEL_LIMIT_ID, weight=STANDARD_REQUEST_COST)]),
    RateLimit(limit_id=GET_ACCOUNT_OVERVIEW_PATH_URL, limit=DECIBEL_API_LIMIT, time_interval=DECIBEL_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=DECIBEL_LIMIT_ID, weight=HEAVY_REQUEST_COST)]),
    RateLimit(limit_id=GET_ACCOUNT_POSITIONS_PATH_URL, limit=DECIBEL_API_LIMIT, time_interval=DECIBEL_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=DECIBEL_LIMIT_ID, weight=HEAVY_REQUEST_COST)]),
    RateLimit(limit_id=GET_ORDER_PATH_URL, limit=DECIBEL_API_LIMIT, time_interval=DECIBEL_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=DECIBEL_LIMIT_ID, weight=STANDARD_REQUEST_COST)]),
    RateLimit(limit_id=GET_USER_TRADE_HISTORY_PATH_URL, limit=DECIBEL_API_LIMIT, time_interval=DECIBEL_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=DECIBEL_LIMIT_ID, weight=HEAVY_REQUEST_COST)]),
    RateLimit(limit_id=GET_USER_FUNDING_HISTORY_PATH_URL, limit=DECIBEL_API_LIMIT, time_interval=DECIBEL_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=DECIBEL_LIMIT_ID, weight=HEAVY_REQUEST_COST)]),
]
