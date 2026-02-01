from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "weex"
DEFAULT_DOMAIN = "com"

HBOT_ORDER_ID_PREFIX = "x-MG43PCSN"
MAX_ORDER_ID_LEN = 40

# Event types (internal)
TRADE_EVENT_TYPE = "trade"
SNAPSHOT_EVENT_TYPE = "snapshot"
DIFF_EVENT_TYPE = "diff"
ORDER_BOOK_DEPTH_EVENT_TYPE = "depth"

# Base URLs (domain-keyed)
REST_URLS = {"com": "https://api-spot.weex.com"}
WS_PUBLIC_URLS = {"com": "wss://ws-spot.weex.com/v2/ws/public"}
WS_PRIVATE_URLS = {"com": "wss://ws-spot.weex.com/v2/ws/private"}

# REST paths
TRADING_PAIRS_PATH_URL = "/api/v2/public/products"
EXCHANGE_INFO_PATH_URL = "/api/v2/public/exchangeInfo"
ORDER_BOOK_SNAPSHOT_PATH_URL = "/api/v2/market/depth"
ACCOUNTS_PATH_URL = "/api/v2/account/assets"

CREATE_ORDER_PATH_URL = "/api/v2/trade/orders"
BATCH_ORDERS_PATH_URL = "/api/v2/trade/batch-orders"
CANCEL_ORDER_PATH_URL = "/api/v2/trade/cancel-order"
BATCH_CANCEL_ORDERS_PATH_URL = "/api/v2/trade/cancel-batch-orders"
ORDER_STATUS_PATH_URL = "/api/v2/trade/orderInfo"
OPEN_ORDERS_PATH_URL = "/api/v2/trade/open-orders"
FILLS_PATH_URL = "/api/v2/trade/fills"
MY_TRADES_PATH_URL = "/api/v2/trade/fills"  # WEEX uses fills endpoint for trades
HISTORY_PATH_URL = "/api/v2/trade/history"
TICKER_PRICE_CHANGE_PATH_URL = "/api/v2/market/ticker"
TICKERS_PATH_URL = "/api/v2/market/tickers"
SERVER_TIME_PATH_URL = "/api/v2/public/time"

# Optional aliases if your code references generic names
SNAPSHOT_PATH_URL = ORDER_BOOK_SNAPSHOT_PATH_URL

# WebSocket URLs
WSS_URL = WS_PUBLIC_URLS[DEFAULT_DOMAIN]  # Alias for compatibility
WS_HEARTBEAT_TIME_INTERVAL = 30

# WS signing path
WS_PRIVATE_REQUEST_PATH = "/v2/ws/private"

# Response helper
SUCCESS_CODE = "00000"

# WEEX trading parameters
SIDE_BUY = "buy"
SIDE_SELL = "sell"

FORCE_NORMAL = "normal"
FORCE_POST_ONLY = "postOnly"
FORCE_FOK = "fok"
FORCE_IOC = "ioc"

# Order States - Map WEEX order statuses to Hummingbot OrderState
ORDER_STATE = {
    "PENDING": OrderState.PENDING_CREATE,
    "NEW": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "PENDING_CANCEL": OrderState.OPEN,
    "CANCELED": OrderState.CANCELED,
    "CANCELLED": OrderState.CANCELED,  # Alternative spelling
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.FAILED,
    "EXPIRED_IN_MATCH": OrderState.FAILED,
}

# Throttle IDs (recommended strategy)

GLOBAL_LIMIT_ID = "GLOBAL"
GLOBAL_BURST_LIMIT_ID = "GLOBAL_BURST"  # 1-second burst protection
TRADING_RULES_LIMIT_ID = "TRADING_RULES"
TRADING_PAIRS_LIMIT_ID = "TRADING_PAIRS"
EXCHANGE_INFO_LIMIT_ID = "EXCHANGE_INFO"
ORDER_BOOK_SNAPSHOT_LIMIT_ID = "ORDER_BOOK_SNAPSHOT"
ACCOUNTS_LIMIT_ID = "ACCOUNTS"
CREATE_ORDER_LIMIT_ID = "CREATE_ORDER"
BATCH_ORDERS_LIMIT_ID = "BATCH_ORDERS"
CANCEL_ORDER_LIMIT_ID = "CANCEL_ORDER"
BATCH_CANCEL_ORDERS_LIMIT_ID = "BATCH_CANCEL_ORDERS"
ORDER_STATUS_LIMIT_ID = "ORDER_STATUS"
OPEN_ORDERS_LIMIT_ID = "OPEN_ORDERS"
FILLS_LIMIT_ID = "FILLS"
MY_TRADES_LIMIT_ID = "MY_TRADES"
TICKER_PRICE_CHANGE_LIMIT_ID = "TICKER_PRICE_CHANGE"

# Time intervals
# WEEX Rate Limit: Weight-based system with 500 weight units per 10 seconds per endpoint
# Each endpoint has individual Weight(IP) and Weight(UID) values
# Default fallback: 10 requests/second unless endpoint specifies otherwise
# Source: https://www.weex.com/api-doc/spot/QuickStart/LIMITS
# Source: https://www.weex.com/api-doc/spot/QuickStart/AccessRestrictions
ONE_SECOND = 1
TWO_SECONDS = 2
TEN_SECONDS = 10
PUBLIC_MAX_REQUEST = 500   # 500 weight units per 10 seconds (public endpoints)
PRIVATE_MAX_REQUEST = 500  # 500 weight units per 10 seconds (private endpoints)

RATE_LIMITS = [
    # Global UID weight pool: 500 weight units per 10 seconds (applies to ALL authenticated endpoints)
    # Based on official WEEX documentation: "Each endpoint with UID limits has an independent 500 every 10 second limit"
    RateLimit(limit_id=GLOBAL_LIMIT_ID, limit=PRIVATE_MAX_REQUEST, time_interval=TEN_SECONDS, weight=1),

    # CRITICAL: WEEX also enforces a burst limit (evidenced by 429 errors after ~50 weight in 3 seconds)
    # The "10 requests/second" statement implies ~50 weight/second burst limit (10 requests × avg weight 5)
    # This prevents rapid-fire API calls from exhausting the pool
    RateLimit(limit_id=GLOBAL_BURST_LIMIT_ID, limit=50, time_interval=ONE_SECOND, weight=1),

    # Public endpoints (assumed weight=1 each, no specific weights documented)
    RateLimit(limit_id=TRADING_PAIRS_PATH_URL, limit=PUBLIC_MAX_REQUEST, time_interval=TEN_SECONDS, weight=1),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=PUBLIC_MAX_REQUEST, time_interval=TEN_SECONDS, weight=1),
    RateLimit(limit_id=ORDER_BOOK_SNAPSHOT_PATH_URL, limit=PUBLIC_MAX_REQUEST, time_interval=TEN_SECONDS, weight=1),
    RateLimit(limit_id=TICKER_PRICE_CHANGE_PATH_URL, limit=PUBLIC_MAX_REQUEST, time_interval=TEN_SECONDS, weight=1),
    RateLimit(limit_id=TICKERS_PATH_URL, limit=PUBLIC_MAX_REQUEST, time_interval=TEN_SECONDS, weight=1),
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=PUBLIC_MAX_REQUEST, time_interval=TEN_SECONDS, weight=1),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=PUBLIC_MAX_REQUEST, time_interval=TEN_SECONDS, weight=1),
    RateLimit(limit_id=TRADING_RULES_LIMIT_ID, limit=PUBLIC_MAX_REQUEST, time_interval=TEN_SECONDS, weight=1),
    RateLimit(limit_id=TRADING_PAIRS_LIMIT_ID, limit=PUBLIC_MAX_REQUEST, time_interval=TEN_SECONDS, weight=1),
    RateLimit(limit_id=ORDER_BOOK_SNAPSHOT_LIMIT_ID, limit=PUBLIC_MAX_REQUEST, time_interval=TEN_SECONDS, weight=1),

    # Private endpoints - Weight(UID) values from official WEEX API documentation
    # Each endpoint linked to BOTH:
    #   - GLOBAL_LIMIT_ID: 500 weight/10s pool
    #   - GLOBAL_BURST_LIMIT_ID: 50 weight/1s burst protection

    # GET /api/v2/account/assets - Weight(UID): 5
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=PRIVATE_MAX_REQUEST, time_interval=TEN_SECONDS, weight=5,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 5), LinkedLimitWeightPair(GLOBAL_BURST_LIMIT_ID, 5)]),
    # POST /api/v2/trade/orders - Weight(UID): 5
    RateLimit(limit_id=CREATE_ORDER_PATH_URL, limit=PRIVATE_MAX_REQUEST, time_interval=TEN_SECONDS, weight=5,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 5), LinkedLimitWeightPair(GLOBAL_BURST_LIMIT_ID, 5)]),
    # POST /api/v2/trade/batch-orders - Weight(UID): 10
    RateLimit(limit_id=BATCH_ORDERS_PATH_URL, limit=PRIVATE_MAX_REQUEST, time_interval=TEN_SECONDS, weight=10,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 10), LinkedLimitWeightPair(GLOBAL_BURST_LIMIT_ID, 10)]),
    # POST /api/v2/trade/cancel-order - Weight(UID): 3
    RateLimit(limit_id=CANCEL_ORDER_PATH_URL, limit=PRIVATE_MAX_REQUEST, time_interval=TEN_SECONDS, weight=3,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 3), LinkedLimitWeightPair(GLOBAL_BURST_LIMIT_ID, 3)]),
    # POST /api/v2/trade/cancel-batch-orders - Weight(UID): 10
    RateLimit(limit_id=BATCH_CANCEL_ORDERS_PATH_URL, limit=PRIVATE_MAX_REQUEST, time_interval=TEN_SECONDS, weight=10,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 10), LinkedLimitWeightPair(GLOBAL_BURST_LIMIT_ID, 10)]),
    # POST /api/v2/trade/orderInfo - Weight(UID): 2
    RateLimit(limit_id=ORDER_STATUS_PATH_URL, limit=PRIVATE_MAX_REQUEST, time_interval=TEN_SECONDS, weight=2,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 2), LinkedLimitWeightPair(GLOBAL_BURST_LIMIT_ID, 2)]),
    # POST /api/v2/trade/open-orders - Weight(UID): 3
    RateLimit(limit_id=OPEN_ORDERS_PATH_URL, limit=PRIVATE_MAX_REQUEST, time_interval=TEN_SECONDS, weight=3,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 3), LinkedLimitWeightPair(GLOBAL_BURST_LIMIT_ID, 3)]),
    # POST /api/v2/trade/fills - Weight(UID): 5
    RateLimit(limit_id=FILLS_PATH_URL, limit=PRIVATE_MAX_REQUEST, time_interval=TEN_SECONDS, weight=5,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 5), LinkedLimitWeightPair(GLOBAL_BURST_LIMIT_ID, 5)]),
    # POST /api/v2/trade/fills (same endpoint for my_trades)
    RateLimit(limit_id=MY_TRADES_PATH_URL, limit=PRIVATE_MAX_REQUEST, time_interval=TEN_SECONDS, weight=5,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 5), LinkedLimitWeightPair(GLOBAL_BURST_LIMIT_ID, 5)]),
    # POST /api/v2/trade/history - Weight(UID): 10
    RateLimit(limit_id=HISTORY_PATH_URL, limit=PRIVATE_MAX_REQUEST, time_interval=TEN_SECONDS, weight=10,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 10), LinkedLimitWeightPair(GLOBAL_BURST_LIMIT_ID, 10)]),

    # Limit ID aliases (for backward compatibility with code using these IDs)
    RateLimit(limit_id=ACCOUNTS_LIMIT_ID, limit=PRIVATE_MAX_REQUEST, time_interval=TEN_SECONDS, weight=5,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 5), LinkedLimitWeightPair(GLOBAL_BURST_LIMIT_ID, 5)]),
    RateLimit(limit_id=CREATE_ORDER_LIMIT_ID, limit=PRIVATE_MAX_REQUEST, time_interval=TEN_SECONDS, weight=5,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 5), LinkedLimitWeightPair(GLOBAL_BURST_LIMIT_ID, 5)]),
    RateLimit(limit_id=BATCH_ORDERS_LIMIT_ID, limit=PRIVATE_MAX_REQUEST, time_interval=TEN_SECONDS, weight=10,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 10), LinkedLimitWeightPair(GLOBAL_BURST_LIMIT_ID, 10)]),
    RateLimit(limit_id=CANCEL_ORDER_LIMIT_ID, limit=PRIVATE_MAX_REQUEST, time_interval=TEN_SECONDS, weight=3,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 3), LinkedLimitWeightPair(GLOBAL_BURST_LIMIT_ID, 3)]),
    RateLimit(limit_id=BATCH_CANCEL_ORDERS_LIMIT_ID, limit=PRIVATE_MAX_REQUEST, time_interval=TEN_SECONDS, weight=10,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 10), LinkedLimitWeightPair(GLOBAL_BURST_LIMIT_ID, 10)]),
    RateLimit(limit_id=ORDER_STATUS_LIMIT_ID, limit=PRIVATE_MAX_REQUEST, time_interval=TEN_SECONDS, weight=2,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 2), LinkedLimitWeightPair(GLOBAL_BURST_LIMIT_ID, 2)]),
    RateLimit(limit_id=OPEN_ORDERS_LIMIT_ID, limit=PRIVATE_MAX_REQUEST, time_interval=TEN_SECONDS, weight=3,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 3), LinkedLimitWeightPair(GLOBAL_BURST_LIMIT_ID, 3)]),
    RateLimit(limit_id=FILLS_LIMIT_ID, limit=PRIVATE_MAX_REQUEST, time_interval=TEN_SECONDS, weight=5,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 5), LinkedLimitWeightPair(GLOBAL_BURST_LIMIT_ID, 5)]),
    RateLimit(limit_id=MY_TRADES_LIMIT_ID, limit=PRIVATE_MAX_REQUEST, time_interval=TEN_SECONDS, weight=5,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 5), LinkedLimitWeightPair(GLOBAL_BURST_LIMIT_ID, 5)]),
    RateLimit(limit_id=TICKER_PRICE_CHANGE_LIMIT_ID, limit=PUBLIC_MAX_REQUEST, time_interval=TEN_SECONDS, weight=1),
]
