from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

EXCHANGE_NAME = "lmex"
DEFAULT_DOMAIN = ""
DOMAIN_SANDBOX = "sandbox"
HBOT_BROKER_ID = "hummingbot"
HBOT_ORDER_ID_PREFIX = "HBOT-"
MAX_ORDER_ID_LEN = 36  # LMEX accepts up to 36 chars for clOrderID

# REST URLs
REST_URLS = {
    DEFAULT_DOMAIN: "https://api.lmex.io/spot",
    DOMAIN_SANDBOX: "https://test-api.lmex.io/spot",
}
API_VERSION = "v3.2"
API_PATH_PREFIX = f"/api/{API_VERSION}"

# Endpoint paths (relative to base URL, without leading slash for Hummingbot pattern)
NETWORK_CHECK_PATH_URL = f"api/{API_VERSION}/time"
SYMBOL_PATH_URL = f"api/{API_VERSION}/market_summary"
ORDER_BOOK_PATH_URL = f"api/{API_VERSION}/orderbook/L2"
TRADES_PATH_URL = f"api/{API_VERSION}/trades"
SERVER_TIME_PATH_URL = f"api/{API_VERSION}/time"
ORDER_PATH_URL = f"api/{API_VERSION}/order"
OPEN_ORDERS_PATH_URL = f"api/{API_VERSION}/user/open_orders"
TRADE_HISTORY_PATH_URL = f"api/{API_VERSION}/user/trade_history"
USER_WALLET_PATH_URL = f"api/{API_VERSION}/user/wallet"
USER_FEES_PATH_URL = f"api/{API_VERSION}/user/fees"

# Order status codes
ORDER_STATUS_INSERTED = 2
ORDER_STATUS_FULLY_TRANSACTED = 4
ORDER_STATUS_PARTIALLY_TRANSACTED = 5
ORDER_STATUS_CANCELLED = 6
ORDER_STATUS_REFUNDED = 7
ORDER_STATUS_INSUFFICIENT_BALANCE = 8
ORDER_STATUS_TRIGGER_INSERTED = 9
ORDER_STATUS_TRIGGER_ACTIVATED = 10
ORDER_STATUS_REJECTED = 15
ORDER_STATUS_NOT_FOUND = 16
ORDER_STATUS_REQUEST_FAILED = 17
ORDER_STATUS_ACTIVE = 65
ORDER_STATUS_PROCESSING = 85
ORDER_STATUS_INACTIVE = 88

# Order type codes
ORDER_TYPE_LIMIT = 76
ORDER_TYPE_MARKET = 77
ORDER_TYPE_PEG = 80

# Open status codes (order is still active/open)
OPEN_ORDER_STATUS_CODES = {
    ORDER_STATUS_INSERTED,
    ORDER_STATUS_PARTIALLY_TRANSACTED,
    ORDER_STATUS_TRIGGER_INSERTED,
    ORDER_STATUS_TRIGGER_ACTIVATED,
    ORDER_STATUS_ACTIVE,
    ORDER_STATUS_PROCESSING,
    ORDER_STATUS_INACTIVE,
}

# Terminal status codes
FILLED_STATUS_CODES = {ORDER_STATUS_FULLY_TRANSACTED}
CANCELLED_STATUS_CODES = {
    ORDER_STATUS_CANCELLED,
    ORDER_STATUS_REFUNDED,
}
FAILED_STATUS_CODES = {
    ORDER_STATUS_INSUFFICIENT_BALANCE,
    ORDER_STATUS_REJECTED,
    ORDER_STATUS_REQUEST_FAILED,
}

# Timeouts
MESSAGE_TIMEOUT = 30.0
API_CALL_TIMEOUT = 10.0
API_MAX_RETRIES = 4

# Intervals
SHORT_POLL_INTERVAL = 5.0
LONG_POLL_INTERVAL = 30.0
UPDATE_ORDER_STATUS_INTERVAL = 10.0
INTERVAL_TRADING_RULES = 600

# Rate limit IDs
PUBLIC_REST_LIMIT_ID = "PublicRest"
PRIVATE_REST_LIMIT_ID = "PrivateRest"
ORDER_WRITE_LIMIT_ID = "OrderWrite"

RATE_LIMITS = [
    RateLimit(limit_id=PUBLIC_REST_LIMIT_ID, limit=15, time_interval=1),
    RateLimit(limit_id=PRIVATE_REST_LIMIT_ID, limit=15, time_interval=1),
    RateLimit(limit_id=ORDER_WRITE_LIMIT_ID, limit=75, time_interval=1),
    # Per-endpoint limits
    RateLimit(
        limit_id=NETWORK_CHECK_PATH_URL,
        limit=15,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=SYMBOL_PATH_URL,
        limit=15,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=ORDER_BOOK_PATH_URL,
        limit=15,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=TRADES_PATH_URL,
        limit=15,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=SERVER_TIME_PATH_URL,
        limit=15,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=ORDER_PATH_URL,
        limit=75,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ORDER_WRITE_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=OPEN_ORDERS_PATH_URL,
        limit=15,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=TRADE_HISTORY_PATH_URL,
        limit=15,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=USER_WALLET_PATH_URL,
        limit=15,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=USER_FEES_PATH_URL,
        limit=15,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_REST_LIMIT_ID)],
    ),
]
