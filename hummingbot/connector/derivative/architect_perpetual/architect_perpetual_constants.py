from hummingbot.core.api_throttler.data_types import RateLimit

EXCHANGE_NAME = "architect_perpetual"
DOMAIN = "sandbox"

# Base URLs (best-effort defaults; can be overridden via domain in web_utils)
DEFAULT_REST_BASE_URL = "https://api.sandbox.x.architect.co"
DEFAULT_WSS_BASE_URL = "wss://ws.sandbox.x.architect.co"

# REST endpoints (best-effort; used by unit tests with mocked responses)
PING_URL = "/api/v1/ping"
EXCHANGE_INFO_URL = "/api/v1/exchangeInfo"
TICKER_BOOK_URL = "/api/v1/ticker/bookTicker"
SERVER_TIME_URL = "/api/v1/time"

ACCOUNT_INFO_URL = "/api/v1/account"
POSITION_INFO_URL = "/api/v1/positionRisk"
ORDER_URL = "/api/v1/order"
OPEN_ORDERS_URL = "/api/v1/openOrders"
MY_TRADES_URL = "/api/v1/userTrades"

# WS endpoints
PUBLIC_WS_PATH = "/ws"
PRIVATE_WS_PATH = "/ws-auth"

# Trading parameters
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = 32

# Error codes (placeholders)
ORDER_NOT_EXIST_ERROR_CODE = 404
ORDER_NOT_EXIST_MESSAGE = "order not found"
UNKNOWN_ORDER_ERROR_CODE = 400
UNKNOWN_ORDER_MESSAGE = "unknown order"

# Rate limits (conservative; not enforced in unit tests)
RATE_LIMITS = [
    RateLimit(limit_id="REST", limit=1200, time_interval=60),
    RateLimit(limit_id="WS", limit=300, time_interval=60),
]
