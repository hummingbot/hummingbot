from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "backpack"
DOMAIN = "backpack"

# Base URLs
REST_URL = "https://api.backpack.exchange"
WS_URL = "wss://ws.backpack.exchange"

# Public REST Endpoints
ASSETS_URL = "/api/v1/assets"
MARKETS_URL = "/api/v1/markets"
TICKERS_URL = "/api/v1/tickers"
TICKER_URL = "/api/v1/ticker"
DEPTH_URL = "/api/v1/depth"
TRADES_URL = "/api/v1/trades"
KLINES_URL = "/api/v1/klines"
TIME_URL = "/api/v1/time"
STATUS_URL = "/api/v1/status"

# Private REST Endpoints
ACCOUNT_URL = "/api/v1/account"
BALANCES_URL = "/api/v1/capital"
ORDER_URL = "/api/v1/order"
ORDERS_URL = "/api/v1/orders"
OPEN_ORDERS_URL = "/api/v1/orders"
CANCEL_ORDER_URL = "/api/v1/order"
CANCEL_ORDERS_URL = "/api/v1/orders"
ORDER_HISTORY_URL = "/api/v1/orders/history"
FILLS_URL = "/api/v1/fills"

# WebSocket channels
WS_ORDERBOOK_CHANNEL = "depth"
WS_TRADES_CHANNEL = "trades"
WS_TICKER_CHANNEL = "ticker"
WS_ORDERS_CHANNEL = "orders"
WS_BALANCES_CHANNEL = "balances"

# Order ID config
MAX_ORDER_ID_LEN = 36
BROKER_ID = "HB"

# Rate limits (conservative)
RATE_LIMITS = [
    RateLimit(limit_id=ASSETS_URL, limit=10, time_interval=1),
    RateLimit(limit_id=MARKETS_URL, limit=10, time_interval=1),
    RateLimit(limit_id=TICKERS_URL, limit=10, time_interval=1),
    RateLimit(limit_id=TICKER_URL, limit=10, time_interval=1),
    RateLimit(limit_id=DEPTH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=TRADES_URL, limit=10, time_interval=1),
    RateLimit(limit_id=TIME_URL, limit=10, time_interval=1),
    RateLimit(limit_id=BALANCES_URL, limit=10, time_interval=1),
    RateLimit(limit_id=ORDER_URL, limit=10, time_interval=1),
    RateLimit(limit_id=ORDERS_URL, limit=10, time_interval=1),
    RateLimit(limit_id=OPEN_ORDERS_URL, limit=10, time_interval=1),
    RateLimit(limit_id=CANCEL_ORDER_URL, limit=10, time_interval=1),
    RateLimit(limit_id=FILLS_URL, limit=10, time_interval=1),
]

# Order states mapping
ORDER_STATE = {
    "New": OrderState.OPEN,
    "Filled": OrderState.FILLED,
    "PartiallyFilled": OrderState.PARTIALLY_FILLED,
    "Cancelled": OrderState.CANCELED,
    "Expired": OrderState.CANCELED,
    "Rejected": OrderState.FAILED,
}

# Request window (milliseconds)
DEFAULT_WINDOW = 5000
MAX_WINDOW = 60000
