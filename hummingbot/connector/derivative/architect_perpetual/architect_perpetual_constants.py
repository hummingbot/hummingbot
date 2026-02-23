from hummingbot.core.api_throttler.data_types import RateLimit

EXCHANGE_NAME = "architect_perpetual"
DOMAIN = "sandbox"

# Base URLs
DEFAULT_REST_BASE_URL = "https://api.sandbox.x.architect.co"
DEFAULT_WSS_BASE_URL = "wss://ws.sandbox.x.architect.co"

# REST endpoints (Binance-style, best-effort)
PING_URL = "/api/v1/ping"
SERVER_TIME_URL = "/api/v1/time"
EXCHANGE_INFO_URL = "/api/v1/exchangeInfo"

ORDER_BOOK_SNAPSHOT_URL = "/api/v1/depth"  # params: symbol, limit
RECENT_TRADES_URL = "/api/v1/trades"  # params: symbol, limit
TICKER_BOOK_URL = "/api/v1/ticker/bookTicker"  # params: symbol

ACCOUNT_INFO_URL = "/api/v1/account"
POSITION_INFO_URL = "/api/v1/positionRisk"
ORDER_URL = "/api/v1/order"  # get/post/delete
OPEN_ORDERS_URL = "/api/v1/openOrders"
MY_TRADES_URL = "/api/v1/userTrades"

# WS endpoints
PUBLIC_WS_PATH = "/ws"
PRIVATE_WS_PATH = "/ws-auth"

# WS event types (Binance-style, best-effort)
WS_EVENT_TRADE = "trade"
WS_EVENT_DEPTH_UPDATE = "depthUpdate"
WS_EVENT_ORDER_TRADE_UPDATE = "ORDER_TRADE_UPDATE"

# Trading parameters
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = 32

# Error codes/messages (placeholders; exchange-specific)
ORDER_NOT_EXIST_ERROR_CODE = 404
ORDER_NOT_EXIST_MESSAGE = "order not found"
UNKNOWN_ORDER_ERROR_CODE = 400
UNKNOWN_ORDER_MESSAGE = "unknown order"

# Rate limits (conservative defaults)
RATE_LIMITS = [
    RateLimit(limit_id="REST", limit=1200, time_interval=60),
    RateLimit(limit_id="WS", limit=300, time_interval=60),
]
