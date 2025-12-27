from hummingbot.core.api_throttler.data_types import RateLimit

AEVO_BASE_URL = "https://api.aevo.xyz"
AEVO_WS_URL = "wss://ws.aevo.xyz"

# Public Endpoints
SNAPSHOT_PATH_URL = "/order_book"
TICKER_PATH_URL = "/markets"
INSTRUMENT_PATH_URL = "/markets"
TRADES_PATH_URL = "/trades"

# Private Endpoints
ORDER_PATH_URL = "/orders"
ACCOUNT_PATH_URL = "/account"
POSITIONS_PATH_URL = "/positions"

# Websocket Topics
WS_TOPIC_ORDERBOOK = "orderbook"
WS_TOPIC_TRADES = "trades"
WS_TOPIC_TICKER = "ticker"

# Rate Limits
RATE_LIMITS = [
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=100, time_interval=10),
    RateLimit(limit_id=TICKER_PATH_URL, limit=100, time_interval=10),
    RateLimit(limit_id=TRADES_PATH_URL, limit=100, time_interval=10),
    RateLimit(limit_id=ORDER_PATH_URL, limit=50, time_interval=10),
    RateLimit(limit_id=ACCOUNT_PATH_URL, limit=50, time_interval=10),
]
