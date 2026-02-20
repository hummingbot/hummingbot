# Decibel Perpetual connector constants

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

EXCHANGE_NAME = "decibel_perpetual"
DEFAULT_DOMAIN = ""
HBOT_BROKER_ID = "hummingbot"
HBOT_ORDER_ID = "t-HBOT"
MAX_ID_LEN = 30

# REST API URLs
REST_URL = "https://api.netna.aptoslabs.com/decibel"
WS_URL = "wss://api.netna.aptoslabs.com/decibel/ws"

# Account endpoints
GET_ACCOUNT_OVERVIEW = "/api/v1/account_overview"
GET_ACCOUNT_POSITIONS = "/api/v1/account_positions"
GET_ACCOUNT_OPEN_ORDERS = "/api/v1/account_open_orders"
GET_SUBACCOUNTS = "/api/v1/subaccounts"
GET_USER_ORDER_HISTORY = "/api/v1/user_order_history"
GET_USER_TRADE_HISTORY = "/api/v1/user_trade_history"
GET_USER_FUNDING_RATE_HISTORY = "/api/v1/user_funding_rate_history"

# Market data endpoints
GET_ALL_AVAILABLE_MARKETS = "/api/v1/markets"
GET_ASSET_CONTEXTS = "/api/v1/asset_contexts"
GET_CANDLESTICK_OHLC = "/api/v1/ohlc"
GET_MARKET_PRICES = "/api/v1/market_prices"
GET_ORDER_BOOK_DEPTH = "/api/v1/order_book_depth"
GET_TRADES = "/api/v1/trades"

# Order endpoints
PLACE_ORDER = "/api/v1/orders"
CANCEL_ORDER = "/api/v1/orders/{order_id}"
GET_ORDER_STATUS = "/api/v1/orders/{order_id}"

# Bulk orders
GET_BULK_ORDERS = "/api/v1/bulk_orders"
GET_BULK_ORDER_STATUS = "/api/v1/bulk_orders/{bulk_order_id}"
GET_BULK_ORDER_FILLS = "/api/v1/bulk_orders/{bulk_order_id}/fills"

# Timeouts
MESSAGE_TIMEOUT = 30.0
PING_TIMEOUT = 10.0
API_CALL_TIMEOUT = 10.0
API_MAX_RETRIES = 4

# Intervals
SHORT_POLL_INTERVAL = 5.0
LONG_POLL_INTERVAL = 45.0
UPDATE_ORDER_STATUS_INTERVAL = 60.0
INTERVAL_TRADING_RULES = 600

# Rate limits
PUBLIC_API_LIMIT_ID = "PublicAPI"
PRIVATE_API_LIMIT_ID = "PrivateAPI"

RATE_LIMITS = [
    RateLimit(limit_id=PUBLIC_API_LIMIT_ID, limit=300, time_interval=1),
    RateLimit(limit_id=PRIVATE_API_LIMIT_ID, limit=100, time_interval=1),
    # Public endpoints
    RateLimit(limit_id=GET_ALL_AVAILABLE_MARKETS, limit=300, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_API_LIMIT_ID)]),
    RateLimit(limit_id=GET_ASSET_CONTEXTS, limit=300, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_API_LIMIT_ID)]),
    RateLimit(limit_id=GET_MARKET_PRICES, limit=300, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_API_LIMIT_ID)]),
    RateLimit(limit_id=GET_ORDER_BOOK_DEPTH, limit=300, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_API_LIMIT_ID)]),
    RateLimit(limit_id=GET_TRADES, limit=300, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_API_LIMIT_ID)]),
    RateLimit(limit_id=GET_CANDLESTICK_OHLC, limit=300, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_API_LIMIT_ID)]),
    # Private endpoints
    RateLimit(limit_id=GET_ACCOUNT_OVERVIEW, limit=100, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_API_LIMIT_ID)]),
    RateLimit(limit_id=GET_ACCOUNT_POSITIONS, limit=100, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_API_LIMIT_ID)]),
    RateLimit(limit_id=GET_ACCOUNT_OPEN_ORDERS, limit=100, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_API_LIMIT_ID)]),
    RateLimit(limit_id=PLACE_ORDER, limit=100, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_API_LIMIT_ID)]),
    RateLimit(limit_id=CANCEL_ORDER, limit=100, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_API_LIMIT_ID)]),
    RateLimit(limit_id=GET_ORDER_STATUS, limit=100, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_API_LIMIT_ID)]),
    RateLimit(limit_id=GET_USER_ORDER_HISTORY, limit=100, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_API_LIMIT_ID)]),
    RateLimit(limit_id=GET_USER_TRADE_HISTORY, limit=100, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_API_LIMIT_ID)]),
]
