from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

EXCHANGE_NAME = "lmex_perpetual"
DEFAULT_DOMAIN = "lmex_perpetual"
TESTNET_DOMAIN = "lmex_perpetual_testnet"

HBOT_ORDER_ID_PREFIX = "x-HBOT"
MAX_ORDER_ID_LEN = 32

# REST base URLs
REST_URLS = {
    DEFAULT_DOMAIN: "https://api.lmex.io/futures",
    TESTNET_DOMAIN: "https://test-api.lmex.io/futures",
}

# REST API version path prefix
API_VERSION = "api/v2.3"

# ---- Public endpoints ----
MARKET_SUMMARY_PATH_URL = f"{API_VERSION}/market_summary"
ORDER_BOOK_PATH_URL = f"{API_VERSION}/orderbook/L2"
TRADES_PATH_URL = f"{API_VERSION}/trades"
FUNDING_HISTORY_PATH_URL = f"{API_VERSION}/funding_history"

# ---- Authenticated endpoints ----
ORDER_PATH_URL = f"{API_VERSION}/order"
OPEN_ORDERS_PATH_URL = f"{API_VERSION}/user/open_orders"
TRADE_HISTORY_PATH_URL = f"{API_VERSION}/user/trade_history"
USER_WALLET_PATH_URL = f"{API_VERSION}/user/wallet"
POSITIONS_PATH_URL = f"{API_VERSION}/user/positions"
LEVERAGE_PATH_URL = f"{API_VERSION}/leverage"
CLOSE_POSITION_PATH_URL = f"{API_VERSION}/order/close_position"

# ---- Order status codes ----
ORDER_STATUS_INSERTED = 2          # open
ORDER_STATUS_FULLY_TRANSACTED = 4  # filled
ORDER_STATUS_PARTIALLY_TRANSACTED = 5  # partial fill
ORDER_STATUS_CANCELLED = 6         # cancelled
ORDER_STATUS_REFUNDED = 7          # cancelled (refund)
ORDER_STATUS_INSUFFICIENT_BALANCE = 8  # failed
ORDER_STATUS_TRIGGER_INSERTED = 9  # open
ORDER_STATUS_TRIGGER_ACTIVATED = 10  # open
ORDER_STATUS_REJECTED = 15         # failed
ORDER_STATUS_NOT_FOUND = 16
ORDER_STATUS_ACTIVE = 65           # open
ORDER_STATUS_PROCESSING = 85       # open
ORDER_STATUS_INACTIVE = 88         # open

OPEN_ORDER_STATUSES = {
    ORDER_STATUS_INSERTED,
    ORDER_STATUS_TRIGGER_INSERTED,
    ORDER_STATUS_TRIGGER_ACTIVATED,
    ORDER_STATUS_ACTIVE,
    ORDER_STATUS_PROCESSING,
    ORDER_STATUS_INACTIVE,
}
PARTIALLY_FILLED_STATUSES = {ORDER_STATUS_PARTIALLY_TRANSACTED}
FILLED_STATUSES = {ORDER_STATUS_FULLY_TRANSACTED}
CANCELLED_STATUSES = {ORDER_STATUS_CANCELLED, ORDER_STATUS_REFUNDED}
FAILED_STATUSES = {ORDER_STATUS_INSUFFICIENT_BALANCE, ORDER_STATUS_REJECTED}

# ---- Funding settlement ----
# Seconds before/after snapshot that can belong to settlement window
FUNDING_SETTLEMENT_DURATION = (0, 30)

# ---- Intervals (seconds) ----
SHORT_POLL_INTERVAL = 5.0
LONG_POLL_INTERVAL = 30.0
UPDATE_ORDER_STATUS_INTERVAL = 10.0
INTERVAL_TRADING_RULES = 600
FUNDING_FEE_POLL_INTERVAL = 3600  # 1 hour; LMEX has 8h funding cycle

# ---- Rate limit IDs ----
PUBLIC_LIMIT_ID = "LmexPerpPublic"
PRIVATE_LIMIT_ID = "LmexPerpPrivate"

RATE_LIMITS = [
    # Bucket: 15 queries/s for public/query endpoints
    RateLimit(limit_id=PUBLIC_LIMIT_ID, limit=15, time_interval=1),
    # Bucket: 75 orders/s for order management
    RateLimit(limit_id=PRIVATE_LIMIT_ID, limit=75, time_interval=1),
    # Individual endpoint limits (all share from their bucket)
    RateLimit(
        limit_id=MARKET_SUMMARY_PATH_URL,
        limit=15,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=ORDER_BOOK_PATH_URL,
        limit=15,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=TRADES_PATH_URL,
        limit=15,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=FUNDING_HISTORY_PATH_URL,
        limit=15,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=ORDER_PATH_URL,
        limit=75,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=OPEN_ORDERS_PATH_URL,
        limit=15,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=TRADE_HISTORY_PATH_URL,
        limit=15,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=USER_WALLET_PATH_URL,
        limit=15,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=POSITIONS_PATH_URL,
        limit=15,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=LEVERAGE_PATH_URL,
        limit=75,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=CLOSE_POSITION_PATH_URL,
        limit=75,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_LIMIT_ID)],
    ),
]
