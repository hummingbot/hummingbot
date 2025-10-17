# A single source of truth for constant variables related to the exchange
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

# Max order id length for Extended
MAX_ORDER_ID_LEN = 32

PING_TIMEOUT = 15.0
WS_CONNECTION_TIMEOUT = 30.0
DEFAULT_DOMAIN = ""
HBOT_ORDER_ID_PREFIX = "HMBot"

EXCHANGE_NAME = "extended"

# Extended API endpoints - Starknet mainnet
PUBLIC_REST_URL = "https://api.starknet.extended.exchange/"
PRIVATE_REST_URL = "https://api.starknet.extended.exchange/"
WS_URL = "wss://api.starknet.extended.exchange/stream.extended.exchange/v1"
PRIVATE_WS_URL = "wss://api.starknet.extended.exchange/stream.extended.exchange/v1"

# REST API ENDPOINTS - Based on Extended API documentation
# Public endpoints
MARKETS_PATH_URL = "api/v1/info/markets"  # Get markets
MARKET_STATS_PATH_URL = "api/v1/info/markets/stats"  # Get market statistics
ORDER_BOOK_PATH_URL = "api/v1/info/markets/orderbook"  # Get order book
LAST_TRADES_PATH_URL = "api/v1/info/markets/trades"  # Get last trades
CANDLES_PATH_URL = "api/v1/info/markets/candles"  # Get candles
FUNDING_RATES_PATH_URL = "api/v1/info/markets/funding-rates"  # Get funding rates
OPEN_INTEREST_PATH_URL = "api/v1/info/markets/open-interest"  # Get open interest

# Private endpoints
ACCOUNT_DETAILS_PATH_URL = "api/v1/user/account"  # Get account details
BALANCE_PATH_URL = "api/v1/user/balance"  # Get balance
POSITIONS_PATH_URL = "api/v1/user/positions"  # Get positions
POSITIONS_HISTORY_PATH_URL = "api/v1/user/positions/history"  # Get positions history
OPEN_ORDERS_PATH_URL = "api/v1/user/orders"  # Get open orders
ORDERS_HISTORY_PATH_URL = "api/v1/user/orders/history"  # Get orders history
ORDER_PATH_URL = "api/v1/user/orders"  # Create/edit/cancel order
ORDER_BY_ID_PATH_URL = "api/v1/user/orders/{order_id}"  # Get order by ID
TRADES_PATH_URL = "api/v1/user/trades"  # Get trades
FUNDING_PAYMENTS_PATH_URL = "api/v1/user/funding-payments"  # Get funding payments
LEVERAGE_PATH_URL = "api/v1/user/leverage"  # Get/update leverage
FEES_PATH_URL = "api/v1/user/fees"  # Get fees

# WebSocket channels
ORDERBOOK_CHANNEL = "orderbook"
TRADES_CHANNEL = "trades"
FUNDING_RATES_CHANNEL = "funding-rates"
CANDLES_CHANNEL = "candles"
MARK_PRICE_CHANNEL = "mark-price"
INDEX_PRICE_CHANNEL = "index-price"
ACCOUNT_UPDATES_CHANNEL = "account-updates"

# Order states mapping
ORDER_STATE = {
    "pending": OrderState.PENDING_CREATE,
    "open": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "cancelled": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
    "expired": OrderState.CANCELED,
}

# Rate limits - Based on Extended API documentation
# Extended has rate limits per endpoint
ALL_ENDPOINTS_LIMIT = "All"
RATE_LIMITS = [
    RateLimit(limit_id=ALL_ENDPOINTS_LIMIT, limit=100, time_interval=1),
    
    # Public endpoints
    RateLimit(
        limit_id=MARKETS_PATH_URL, 
        limit=100, 
        time_interval=1, 
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]
    ),
    RateLimit(
        limit_id=MARKET_STATS_PATH_URL,
        limit=100,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=ORDER_BOOK_PATH_URL,
        limit=100,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=LAST_TRADES_PATH_URL,
        limit=100,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=CANDLES_PATH_URL,
        limit=100,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=FUNDING_RATES_PATH_URL,
        limit=100,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=OPEN_INTEREST_PATH_URL,
        limit=100,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    
    # Private endpoints
    RateLimit(
        limit_id=ACCOUNT_DETAILS_PATH_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=BALANCE_PATH_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=POSITIONS_PATH_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=POSITIONS_HISTORY_PATH_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=OPEN_ORDERS_PATH_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=ORDERS_HISTORY_PATH_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=ORDER_PATH_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=TRADES_PATH_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=FUNDING_PAYMENTS_PATH_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=LEVERAGE_PATH_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=FEES_PATH_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
]

