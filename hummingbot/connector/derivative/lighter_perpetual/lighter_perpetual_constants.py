from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "lighter_perpetual"
DEFAULT_DOMAIN = "lighter_perpetual"
HB_OT_ID_PREFIX = "HBOT"

# Base URLs
REST_URL = "https://mainnet.zklighter.elliot.ai/api/v1"
WSS_URL = "wss://mainnet.zklighter.elliot.ai/stream"

TESTNET_DOMAIN = "lighter_perpetual_testnet"
TESTNET_REST_URL = "https://testnet.zklighter.elliot.ai/api/v1"
TESTNET_WSS_URL = "wss://testnet.zklighter.elliot.ai/stream"

# order status mapping
ORDER_STATE = {
    "open": OrderState.OPEN,
    "in-progress": OrderState.OPEN,
    "pending": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "cancelled": OrderState.CANCELED,   # British spelling from REST/WS
    "canceled": OrderState.CANCELED,    # American spelling variant (defensive)
    "cancel": OrderState.CANCELED,      # event_type value sometimes used in WS
    "canceled-post-only": OrderState.CANCELED,
    "canceled-reduce-only": OrderState.CANCELED,
    "canceled-position-not-allowed": OrderState.CANCELED,
    "canceled-margin-not-allowed": OrderState.CANCELED,
    "canceled-too-much-slippage": OrderState.CANCELED,
    "canceled-not-enough-liquidity": OrderState.CANCELED,
    "canceled-self-trade": OrderState.CANCELED,
    "canceled-expired": OrderState.CANCELED,
    "canceled-oco": OrderState.CANCELED,
    "canceled-child": OrderState.CANCELED,
    "canceled-liquidation": OrderState.CANCELED,
    "canceled-invalid-balance": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
}

GET_MARKET_ORDER_BOOK_SNAPSHOT_PATH_URL = "/orderBookOrders"
GET_ORDER_HISTORY_PATH_URL = "/accountInactiveOrders"
GET_ACTIVE_ORDERS_PATH_URL = "/accountActiveOrders"
GET_CANDLES_PATH_URL = "/candles"
GET_PRICES_PATH_URL = "/exchangeStats"
GET_FUNDING_RATES_PATH_URL = "/funding-rates"
GET_POSITIONS_PATH_URL = "/positions"
GET_FUNDING_HISTORY_PATH_URL = "/positionFunding"
SET_LEVERAGE_PATH_URL = "/changeAccountTier"
CANCEL_ORDER_PATH_URL = "/sendTx"
EXCHANGE_INFO_PATH_URL = "/orderBooks"
GET_TOKENLIST_PATH_URL = "/tokenlist"
GET_ACCOUNT_INFO_PATH_URL = "/account"
GET_ACCOUNT_API_CONFIG_KEYS = "/apikeys"
CREATE_ACCOUNT_API_CONFIG_KEY = "/tokens_create"
GET_TRADE_HISTORY_PATH_URL = "/trades"
GET_FEES_INFO_PATH_URL = "/leaseOptions"
GET_NEXT_NONCE_PATH_URL = "/nextNonce"

# the API endpoints for market / limit / stop orders are different
# the support for stop orders is out of the scope for this integration
CREATE_MARKET_ORDER_PATH_URL = "/sendTx"
CREATE_LIMIT_ORDER_PATH_URL = "/sendTx"

# Default maximum slippage tolerance for market orders (percentage string, e.g. "5" = 5%)
MARKET_ORDER_MAX_SLIPPAGE = "5"

# WebSocket Channels

WS_ORDER_BOOK_SNAPSHOT_CHANNEL = "order_book"
WS_TRADES_CHANNEL = "trade"
WS_MARKET_STATS_CHANNEL = "market_stats"

WS_ACCOUNT_ORDER_UPDATES_CHANNEL = "account_order_updates"
WS_ACCOUNT_POSITIONS_CHANNEL = "account_positions"
WS_ACCOUNT_INFO_CHANNEL = "account_info"
WS_ACCOUNT_TRADES_CHANNEL = "account_trades"
WS_ACCOUNT_ALL_CHANNEL = "account_all"

WS_PING_INTERVAL = 30  # Keep connection alive

# the exchange has different "costs" of the calls for every endpoint
# plus there're exactly 2 tiers of rate limits: (1) Unidentified IP (2) Valid API Config Key
# below you could find (in the comments) -- the costs (aka "weight") of each endpoints group

LIGHTER_LIMIT_ID = "LIGHTER_LIMIT"

# Default throttler limits derived from the documented Lighter request budget.
LIGHTER_TIER_1_LIMIT = 24000
LIGHTER_TIER_2_LIMIT = 24000
LIGHTER_LIMIT_INTERVAL = 60

FEE_TIER_LIMITS = {
    0: 3000,     # doc: 300
    1: 6000,     # doc: 600
    2: 12000,    # doc: 1200
    3: 24000,    # doc: 2400
    4: 60000,    # doc: 6000
    5: 120000,   # doc: 12000
    6: 240000,   # doc: 24000
    7: 300000,   # doc: 30000
}

# Costs (x10 of doc values)
STANDARD_REQUEST_COST = 10       # doc: 1
ORDER_CANCELLATION_COST = 5      # doc: 0.5
HEAVY_GET_REQUEST_COST_TIER_1 = 120  # Unidentified IP (doc: 12)
HEAVY_GET_REQUEST_COST_TIER_2 = 30   # Valid API Config Key (doc: 3)

RATE_LIMITS = [
    RateLimit(limit_id=LIGHTER_LIMIT_ID, limit=LIGHTER_TIER_1_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL),
    RateLimit(limit_id=GET_MARKET_ORDER_BOOK_SNAPSHOT_PATH_URL, limit=LIGHTER_TIER_1_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_1)]),
    RateLimit(limit_id=CREATE_LIMIT_ORDER_PATH_URL, limit=LIGHTER_TIER_1_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=STANDARD_REQUEST_COST)]),
    RateLimit(limit_id=CREATE_MARKET_ORDER_PATH_URL, limit=LIGHTER_TIER_1_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=STANDARD_REQUEST_COST)]),
    RateLimit(limit_id=CANCEL_ORDER_PATH_URL, limit=LIGHTER_TIER_1_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=ORDER_CANCELLATION_COST)]),
    RateLimit(limit_id=SET_LEVERAGE_PATH_URL, limit=LIGHTER_TIER_1_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=STANDARD_REQUEST_COST)]),
    RateLimit(limit_id=GET_FUNDING_HISTORY_PATH_URL, limit=LIGHTER_TIER_1_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_1)]),
    RateLimit(limit_id=GET_POSITIONS_PATH_URL, limit=LIGHTER_TIER_1_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_1)]),
    RateLimit(limit_id=GET_ORDER_HISTORY_PATH_URL, limit=LIGHTER_TIER_1_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_1)]),
    RateLimit(limit_id=GET_ACTIVE_ORDERS_PATH_URL, limit=LIGHTER_TIER_1_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_1)]),
    RateLimit(limit_id=GET_CANDLES_PATH_URL, limit=LIGHTER_TIER_1_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_1)]),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=LIGHTER_TIER_1_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_1)]),
    RateLimit(limit_id=GET_PRICES_PATH_URL, limit=LIGHTER_TIER_1_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_1)]),
    RateLimit(limit_id=GET_FUNDING_RATES_PATH_URL, limit=LIGHTER_TIER_1_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_1)]),
    RateLimit(limit_id=GET_ACCOUNT_INFO_PATH_URL, limit=LIGHTER_TIER_1_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_1)]),
    RateLimit(limit_id=GET_ACCOUNT_API_CONFIG_KEYS, limit=LIGHTER_TIER_1_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_1)]),
    RateLimit(limit_id=CREATE_ACCOUNT_API_CONFIG_KEY, limit=LIGHTER_TIER_1_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_1)]),
    RateLimit(limit_id=GET_TRADE_HISTORY_PATH_URL, limit=LIGHTER_TIER_1_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_1)]),
    RateLimit(limit_id=GET_FEES_INFO_PATH_URL, limit=LIGHTER_TIER_1_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_1)]),
    RateLimit(limit_id=GET_NEXT_NONCE_PATH_URL, limit=LIGHTER_TIER_1_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=STANDARD_REQUEST_COST)]),
    RateLimit(limit_id=GET_TOKENLIST_PATH_URL, limit=LIGHTER_TIER_1_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=STANDARD_REQUEST_COST)]),
]

RATE_LIMITS_TIER_2 = [
    RateLimit(limit_id=LIGHTER_LIMIT_ID, limit=LIGHTER_TIER_2_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL),
    RateLimit(limit_id=GET_MARKET_ORDER_BOOK_SNAPSHOT_PATH_URL, limit=LIGHTER_TIER_2_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_2)]),
    RateLimit(limit_id=CREATE_LIMIT_ORDER_PATH_URL, limit=LIGHTER_TIER_2_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=STANDARD_REQUEST_COST)]),
    RateLimit(limit_id=CREATE_MARKET_ORDER_PATH_URL, limit=LIGHTER_TIER_2_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=STANDARD_REQUEST_COST)]),
    RateLimit(limit_id=CANCEL_ORDER_PATH_URL, limit=LIGHTER_TIER_2_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=ORDER_CANCELLATION_COST)]),
    RateLimit(limit_id=SET_LEVERAGE_PATH_URL, limit=LIGHTER_TIER_2_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=STANDARD_REQUEST_COST)]),
    RateLimit(limit_id=GET_FUNDING_HISTORY_PATH_URL, limit=LIGHTER_TIER_2_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_2)]),
    RateLimit(limit_id=GET_POSITIONS_PATH_URL, limit=LIGHTER_TIER_2_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_2)]),
    RateLimit(limit_id=GET_ORDER_HISTORY_PATH_URL, limit=LIGHTER_TIER_2_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_2)]),
    RateLimit(limit_id=GET_ACTIVE_ORDERS_PATH_URL, limit=LIGHTER_TIER_2_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_2)]),
    RateLimit(limit_id=GET_CANDLES_PATH_URL, limit=LIGHTER_TIER_2_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_2)]),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=LIGHTER_TIER_2_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_2)]),
    RateLimit(limit_id=GET_PRICES_PATH_URL, limit=LIGHTER_TIER_2_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_2)]),
    RateLimit(limit_id=GET_FUNDING_RATES_PATH_URL, limit=LIGHTER_TIER_2_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_2)]),
    RateLimit(limit_id=GET_ACCOUNT_INFO_PATH_URL, limit=LIGHTER_TIER_2_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_2)]),
    RateLimit(limit_id=GET_ACCOUNT_API_CONFIG_KEYS, limit=LIGHTER_TIER_2_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_2)]),
    RateLimit(limit_id=CREATE_ACCOUNT_API_CONFIG_KEY, limit=LIGHTER_TIER_2_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_2)]),
    RateLimit(limit_id=GET_TRADE_HISTORY_PATH_URL, limit=LIGHTER_TIER_2_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_2)]),
    RateLimit(limit_id=GET_FEES_INFO_PATH_URL, limit=LIGHTER_TIER_2_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST_TIER_2)]),
    RateLimit(limit_id=GET_NEXT_NONCE_PATH_URL, limit=LIGHTER_TIER_2_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=STANDARD_REQUEST_COST)]),
    RateLimit(limit_id=GET_TOKENLIST_PATH_URL, limit=LIGHTER_TIER_2_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=STANDARD_REQUEST_COST)]),
]
