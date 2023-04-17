from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = ""

ORDER_ID_PREFIX = ""
MAX_ORDER_ID_LEN = 32

# Base URL
REST_URL_P1 = "https://api.hotbit.io/v2/p1"
REST_URL_P2 = "https://api.hotbit.io/v2/p2"
WSS_URL = "wss://ws.hotbit.io/v2/"

# # Public API endpoints or HotbitClient function
TICKER_PRICE_CHANGE_PATH_URL = "/market.status"
EXCHANGE_INFO_PATH_URL = "/market.list"
CHECK_NETWORK_PATH_URL = "/market.last?market=ETH/BTC"
SNAPSHOT_PATH_URL = "/order.depth"

# # Private API endpoints or HotbitClient function
ACCOUNTS_PATH_URL = "/balance.query"
MY_TRADES_PATH_URL = "/order.finished_detail"
ORDER_PATH_URL = "/order.deals"
ORDER_LIMIT_PATH_URL = "/order.put_limit"
ORDER_CANCEL_PATH_URL = "/order.cancel"
PENDING_ORDER_PATH_URL = "/order.pending"
FINISHED_ORDER_PATH_URL = "/order.finished"

WS_HEARTBEAT_TIME_INTERVAL = 30

DEPTH_PRICE_INTERVAL = "0.0001"
DEPTH_MAX_LIMIT = 100
DEPTH_LISTEN_LIMIT = 10

# # Hotbit params

SIDE_BUY = 2
SIDE_SELL = 1

# # Order States
ORDER_STATE_CREATED = 1
ORDER_STATE_UPDATED = 2
ORDER_STATE_FINISHED = 3
ORDER_STATE = {
    ORDER_STATE_CREATED: OrderState.OPEN,
    ORDER_STATE_UPDATED: OrderState.PARTIALLY_FILLED,
    ORDER_STATE_FINISHED: OrderState.FILLED,
}


FINISHED_STATE_FILLED = 0
FINISHED_STATE_CANCELED = 8
FINISHED_STATE = {
    FINISHED_STATE_FILLED: OrderState.FILLED,
    FINISHED_STATE_CANCELED: OrderState.CANCELED,
}

# # Websocket event types
DIFF_EVENT_TYPE = "depth.update"
TRADE_EVENT_TYPE = "deals.update"
ORDER_EVENT_TYPE = "order.update"
ASSET_EVENT_TYPE = "asset.update"

RATE_LIMITS = [
    RateLimit(limit_id=TICKER_PRICE_CHANGE_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=CHECK_NETWORK_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=MY_TRADES_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=ORDER_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=ORDER_LIMIT_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=ORDER_CANCEL_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=PENDING_ORDER_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=FINISHED_ORDER_PATH_URL, limit=10, time_interval=1)
]
