from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

# Domain names
MAINNET_DOMAIN = "mainnet"
TESTNET_DOMAIN = "testnet"
DEFAULT_DOMAIN = MAINNET_DOMAIN

# Base URLs
REST_URLS = {
    MAINNET_DOMAIN: "https://api.mainnet.aptoslabs.com/decibel",
    TESTNET_DOMAIN: "https://api.testnet.aptoslabs.com/decibel",
}

WS_URLS = {
    MAINNET_DOMAIN: "wss://api.mainnet.aptoslabs.com/decibel/ws",
    TESTNET_DOMAIN: "wss://api.testnet.aptoslabs.com/decibel/ws",
}

# Public REST endpoints
MARKETS_PATH_URL = "/api/v1/markets"
MARKET_PRICES_PATH_URL = "/api/v1/market_prices"
DEPTH_PATH_URL = "/api/v1/depth"
TRADES_PATH_URL = "/api/v1/trades"
SERVER_TIME_PATH_URL = "/api/v1/time"

# Private REST endpoints (require bearer token)
ACCOUNT_OVERVIEW_PATH_URL = "/api/v1/account_overview"
ACCOUNT_POSITIONS_PATH_URL = "/api/v1/account_positions"
OPEN_ORDERS_PATH_URL = "/api/v1/account_open_orders"
ORDER_PATH_URL = "/api/v1/orders"  # GET one or many, POST create

HEARTBEAT_TIME_INTERVAL = 30.0

# WebSocket topics (see docs.decibel.trade)
WS_DEPTH_TOPIC_PREFIX = "depth"  # depth:{marketAddr}(:{aggregationLevel})
WS_TRADES_TOPIC_PREFIX = "trades"  # trades:{marketAddr}
WS_MARKET_PRICE_TOPIC_PREFIX = "market_price"  # market_price:{marketAddr}
WS_ALL_MARKET_PRICES_TOPIC = "all_market_prices"

WS_ACCOUNT_OPEN_ORDERS_PREFIX = "account_open_orders"  # account_open_orders:{accountAddr}
WS_ORDER_UPDATES_PREFIX = "order_updates"  # order_updates:{accountAddr}
WS_ACCOUNT_POSITIONS_PREFIX = "account_positions"  # account_positions:{accountAddr}
WS_ACCOUNT_OVERVIEW_PREFIX = "account_overview"  # account_overview:{accountAddr}
WS_USER_TRADES_PREFIX = "user_trades"  # user_trades:{accountAddr}

# Rate limits
MAX_REQUEST_WEIGHT = 1200
NO_LIMIT_ID = "NO_LIMIT"
REQUEST_WEIGHT_ID = "REQUEST_WEIGHT"

RATE_LIMITS = [
    RateLimit(limit_id=NO_LIMIT_ID, limit=MAX_REQUEST_WEIGHT, time_interval=60),
    RateLimit(
        limit_id=REQUEST_WEIGHT_ID,
        limit=MAX_REQUEST_WEIGHT,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(NO_LIMIT_ID)],
    ),
    # Public endpoints
    RateLimit(limit_id=MARKETS_PATH_URL, limit=MAX_REQUEST_WEIGHT, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_ID, 1)]),
    RateLimit(limit_id=MARKET_PRICES_PATH_URL, limit=MAX_REQUEST_WEIGHT, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_ID, 1)]),
    RateLimit(limit_id=DEPTH_PATH_URL, limit=MAX_REQUEST_WEIGHT, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_ID, 1)]),
    RateLimit(limit_id=TRADES_PATH_URL, limit=MAX_REQUEST_WEIGHT, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_ID, 1)]),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=MAX_REQUEST_WEIGHT, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_ID, 1)]),
    # Private endpoints
    RateLimit(limit_id=ACCOUNT_OVERVIEW_PATH_URL, limit=MAX_REQUEST_WEIGHT, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_ID, 5)]),
    RateLimit(limit_id=ACCOUNT_POSITIONS_PATH_URL, limit=MAX_REQUEST_WEIGHT, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_ID, 5)]),
    RateLimit(limit_id=OPEN_ORDERS_PATH_URL, limit=MAX_REQUEST_WEIGHT, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_ID, 5)]),
    RateLimit(limit_id=ORDER_PATH_URL, limit=MAX_REQUEST_WEIGHT, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_ID, 10)]),
]
