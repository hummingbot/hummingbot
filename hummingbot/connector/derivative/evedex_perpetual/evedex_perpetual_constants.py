from datetime import datetime, timezone

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URLS = {
    "demo": "https://market-data-api.evedex.tech",
    "prod": "https://market-data-api.evedex.tech",
}

WS_URLS = {
    "demo": "wss://centrifugo.evedex.tech/connection/websocket",
    "prod": "wss://centrifugo.evedex.tech/connection/websocket",
}

AUTH_URLS = {
    "demo": "https://market-data-api.evedex.tech",
    "prod": "https://market-data-api.evedex.tech",
}

ENV_PREFIX = {
    "demo": "futures-perp-demo",
    "prod": "futures-perp",
}

DAY_ZERO = datetime(2025, 7, 24, tzinfo=timezone.utc)

RATE_LIMITS = [
    # Public endpoints
    RateLimit(limit_id="public", limit=100, time_interval=60),
    RateLimit(limit_id="instrument_list", limit=100, time_interval=60, linked_limits=[LinkedLimitWeightPair("public")]),
    RateLimit(limit_id="orderbook_snapshot", limit=100, time_interval=60, linked_limits=[LinkedLimitWeightPair("public")]),
    RateLimit(limit_id="recent_trades", limit=100, time_interval=60, linked_limits=[LinkedLimitWeightPair("public")]),
    
    # Private endpoints
    RateLimit(limit_id="private", limit=50, time_interval=60),
    RateLimit(limit_id="available_balance", limit=50, time_interval=60, linked_limits=[LinkedLimitWeightPair("private")]),
    RateLimit(limit_id="positions", limit=50, time_interval=60, linked_limits=[LinkedLimitWeightPair("private")]),
    RateLimit(limit_id="order_status", limit=50, time_interval=60, linked_limits=[LinkedLimitWeightPair("private")]),
    
    # Order endpoints
    RateLimit(limit_id="orders", limit=30, time_interval=60),
    RateLimit(limit_id="place_order", limit=30, time_interval=60, linked_limits=[LinkedLimitWeightPair("orders")]),
    RateLimit(limit_id="cancel_order", limit=30, time_interval=60, linked_limits=[LinkedLimitWeightPair("orders")]),
    RateLimit(limit_id="replace_order", limit=30, time_interval=60, linked_limits=[LinkedLimitWeightPair("orders")]),
    
    # Auth endpoints
    RateLimit(limit_id="auth", limit=10, time_interval=60),
    RateLimit(limit_id="auth_nonce", limit=10, time_interval=60, linked_limits=[LinkedLimitWeightPair("auth")]),
    RateLimit(limit_id="auth_signup", limit=10, time_interval=60, linked_limits=[LinkedLimitWeightPair("auth")]),
    RateLimit(limit_id="auth_refresh", limit=10, time_interval=60, linked_limits=[LinkedLimitWeightPair("auth")]),
    
    # WebSocket
    RateLimit(limit_id="ws_subscribe", limit=20, time_interval=10),
]

ENDPOINTS = {
    # Market data
    "instrument_list": "/api/market/instrument",
    "orderbook_deep": "/api/market/{instrument}/deep",
    "recent_trades": "/api/market/{instrument}/recent-trades",
    "ticker": "/api/market/{instrument}/ticker",
    
    # Account
    "available_balance": "/api/market/available-balance",
    "positions": "/api/market/positions",
    
    # Orders v2 (signed)
    "order_limit_v2": "/api/v2/order/limit",
    "order_market_v2": "/api/v2/order/market",
    "order_stop_limit_v2": "/api/v2/order/stop-limit",
    "order_mass_limit_v2": "/api/v2/order/mass-limit/{instrument}",
    
    # Order management (cancel is unsigned, replace is signed)
    "order_cancel": "/api/order/{order_id}",
    "order_replace_limit": "/api/order/{order_id}/limit",
    "order_replace_stop": "/api/order/{order_id}/stop-limit",
    "order_status": "/api/order/opened",
    "order_fills": "/api/order/{order_id}/fill",
    
    # Positions
    "position_close_v2": "/api/v2/position/{instrument}/close",
    "position_leverage": "/api/position/{instrument}",
    
    # Auth
    "auth_nonce": "/auth/nonce",
    "auth_signup": "/auth/user/sign-up",
    "auth_refresh": "/auth/refresh",
}

# WebSocket channel templates
WS_CHANNELS = {
    "heartbeat": "{env}:heartbeat",
    "info": "{env}:info",
    "instruments": "{env}:instruments",
    "funding_rate": "{env}:funding-rate",
    "orderbook_diff": "{env}:orderBook-{instrument}-0.1",
    "orderbook_best": "{env}:orderBook-{instrument}-best",
    "recent_trades": "{env}:recent-trade-{instrument}",
    
    # Private channels (require authentication)
    "user": "user-{user_id}",
    "funding": "funding-{user_id}",
    "position": "position-{user_id}",
    "order": "order-{user_id}",
    "order_fills": "orderFills-{user_id}",
    "order_fee": "order-fee-{user_id}",
    "tpsl": "tpsl-{user_id}",
}

# EVEDEX -> Hummingbot
ORDER_STATUS_MAP = {
    "NEW": "open",
    "PARTIALLY_FILLED": "partially_filled",
    "FILLED": "filled",
    "CANCELLED": "cancelled",
    "REJECTED": "failed",
    "EXPIRED": "cancelled",
}

ORDER_SIDE_MAP = {
    "buy": "BUY",
    "sell": "SELL",
}

ORDER_TYPE_MAP = {
    "limit": "LIMIT",
    "market": "MARKET",
    "limit_maker": "LIMIT_MAKER",
}

# Default trading fees
DEFAULT_FEES = {
    "maker_percent_fee": 0.02,
    "taker_percent_fee": 0.05,
}

MIN_ORDER_SIZE = {
    "BTC-USD": 0.001,
    "ETH-USD": 0.01,
}

WS_HEARTBEAT_INTERVAL = 30
WS_RECONNECT_DELAY = 5
HTTP_TIMEOUT = 30
MAX_RETRIES = 3

CONNECTOR_NAME = "evedex"

INSTRUMENT_PRICE_SCALE_KEY = "priceScale"
INSTRUMENT_QTY_SCALE_KEY = "quantityScale"
INSTRUMENT_TICK_SIZE_KEY = "tickSize"
INSTRUMENT_LOT_SIZE_KEY = "lotSize"
