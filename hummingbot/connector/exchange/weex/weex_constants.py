from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "weex"
DEFAULT_DOMAIN = "weex"

HBOT_ORDER_ID_PREFIX = "x-MG43PCSN"
MAX_ORDER_ID_LEN = 32

# Event types (internal)
TRADE_EVENT_TYPE = "trade"
SNAPSHOT_EVENT_TYPE = "snapshot"
DIFF_EVENT_TYPE = "diff"
ORDER_BOOK_DEPTH_EVENT_TYPE = "depth"

# Base URLs (domain-keyed)
REST_URLS = {DEFAULT_DOMAIN: "https://api-spot.weex.com"}
WS_PUBLIC_URLS = {DEFAULT_DOMAIN: "wss://ws-spot.weex.com/v2/ws/public"}
WS_PRIVATE_URLS = {DEFAULT_DOMAIN: "wss://ws-spot.weex.com/v2/ws/private"}

# REST paths
TRADING_PAIRS_PATH_URL = "/api/v2/public/products"
EXCHANGE_INFO_PATH_URL = "/api/v2/public/exchangeInfo"
ORDER_BOOK_SNAPSHOT_PATH_URL = "/api/v2/market/depth"
ACCOUNTS_PATH_URL = "/api/v2/account/assets"

CREATE_ORDER_PATH_URL = "/api/v2/trade/orders"
CANCEL_ORDER_PATH_URL = "/api/v2/trade/cancel-order"
ORDER_STATUS_PATH_URL = "/api/v2/trade/orderInfo"
OPEN_ORDERS_PATH_URL = "/api/v2/trade/open-orders"
FILLS_PATH_URL = "/api/v2/trade/fills"
MY_TRADES_PATH_URL = "/api/v2/trade/fills"  # WEEX uses fills endpoint for trades
HISTORY_PATH_URL = "/api/v2/trade/history"
TICKER_PRICE_CHANGE_PATH_URL = "/api/v2/market/ticker"
TICKERS_PATH_URL = "/api/v2/market/tickers"

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
SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

TIME_IN_FORCE_GTC = "GTC"  # Good till cancelled
TIME_IN_FORCE_IOC = "IOC"  # Immediate or cancel
TIME_IN_FORCE_FOK = "FOK"  # Fill or kill

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
TRADING_RULES_LIMIT_ID = "TRADING_RULES"
TRADING_PAIRS_LIMIT_ID = "TRADING_PAIRS"
ORDER_BOOK_SNAPSHOT_LIMIT_ID = "ORDER_BOOK_SNAPSHOT"
ACCOUNTS_LIMIT_ID = "ACCOUNTS"
CREATE_ORDER_LIMIT_ID = "CREATE_ORDER"
CANCEL_ORDER_LIMIT_ID = "CANCEL_ORDER"
ORDER_STATUS_LIMIT_ID = "ORDER_STATUS"
OPEN_ORDERS_LIMIT_ID = "OPEN_ORDERS"
FILLS_LIMIT_ID = "FILLS"
MY_TRADES_LIMIT_ID = "MY_TRADES"
TICKER_PRICE_CHANGE_LIMIT_ID = "TICKER_PRICE_CHANGE"

# Time intervals
ONE_MINUTE = 60
MAX_REQUEST = 5000

RATE_LIMITS = [
    # Pool limits
    RateLimit(limit_id=GLOBAL_LIMIT_ID, limit=1200, time_interval=ONE_MINUTE, weight=1),
    
    # Weighted limits
    RateLimit(limit_id=TRADING_RULES_LIMIT_ID, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=1,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 1)]),
    RateLimit(limit_id=TRADING_PAIRS_LIMIT_ID, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=1,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 1)]),
    RateLimit(limit_id=ORDER_BOOK_SNAPSHOT_LIMIT_ID, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=1,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 1)]),
    RateLimit(limit_id=ACCOUNTS_LIMIT_ID, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=1,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 1)]),
    RateLimit(limit_id=CREATE_ORDER_LIMIT_ID, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=1,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 1)]),
    RateLimit(limit_id=CANCEL_ORDER_LIMIT_ID, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=1,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 1)]),
    RateLimit(limit_id=ORDER_STATUS_LIMIT_ID, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=1,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 1)]),
    RateLimit(limit_id=OPEN_ORDERS_LIMIT_ID, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=1,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 1)]),
    RateLimit(limit_id=FILLS_LIMIT_ID, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=1,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 1)]),
    RateLimit(limit_id=MY_TRADES_LIMIT_ID, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=1,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 1)]),
    RateLimit(limit_id=TICKER_PRICE_CHANGE_LIMIT_ID, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=1,
              linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 1)]),
]
