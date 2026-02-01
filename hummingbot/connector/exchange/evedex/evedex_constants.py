from hummingbot.core.api_throttler.data_types import RateLimit

EXCHANGE_NAME = "evedex"

DEFAULT_DOMAIN = "evedex"

# Base URLs
REST_URL = "https://trading-api.evedex.com"
AUTH_URL = "https://auth-api.evedex.com"
WSS_URL = "wss://ws.evedex.com/connection/websocket"

# Chain ID for EIP-712 signing (Prod)
CHAIN_ID = 161803

# API Endpoints
# Public
CHECK_NETWORK_PATH_URL = "/instruments"  # Using instruments as a health check since ping might not be exposed
INSTRUMENTS_PATH_URL = "/instruments"
ORDER_BOOK_PATH_URL = "/market/depth"
RECENT_TRADES_PATH_URL = "/market/trades"
FUNDING_INFO_PATH_URL = "/funding/info"

# Private
USER_SELF_PATH_URL = "/user/me"
ORDER_PATH_URL = "/order"
POSITIONS_PATH_URL = "/position"
ACCOUNT_BALANCE_PATH_URL = "/user/balance"

HBOT_BROKER_ID = "HBOT"

# Rate Limits (Placeholder values, need to verify with docs)
RATE_LIMITS = [
    RateLimit(limit_id=REST_URL, limit=100, time_interval=1),
    RateLimit(limit_id=AUTH_URL, limit=50, time_interval=1),
    RateLimit(limit_id=CHECK_NETWORK_PATH_URL, limit=100, time_interval=1),
    RateLimit(limit_id=INSTRUMENTS_PATH_URL, limit=100, time_interval=1),
    RateLimit(limit_id=ORDER_BOOK_PATH_URL, limit=100, time_interval=1),
    RateLimit(limit_id=RECENT_TRADES_PATH_URL, limit=100, time_interval=1),
    RateLimit(limit_id=FUNDING_INFO_PATH_URL, limit=100, time_interval=1),
    RateLimit(limit_id=USER_SELF_PATH_URL, limit=100, time_interval=1),
    RateLimit(limit_id=ORDER_PATH_URL, limit=100, time_interval=1),
    RateLimit(limit_id=POSITIONS_PATH_URL, limit=100, time_interval=1),
    RateLimit(limit_id=ACCOUNT_BALANCE_PATH_URL, limit=100, time_interval=1),
]

WS_PING_TIMEOUT = 20.0

# Centrifuge channel prefix (from SDK params.ts)
CENTRIFUGE_PREFIX = "futures-perp"
