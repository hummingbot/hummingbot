from enum import Enum

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionMode
from hummingbot.core.data_type.in_flight_order import OrderState


class MarginMode(Enum):
    CROSS = "CROSS"
    ISOLATED = "ISOLATED"


EXCHANGE_NAME = "backpack_perpetual"
DEFAULT_DOMAIN = "backpack.exchange"
REST_URL = "https://api.backpack.exchange"
WSS_URL = "wss://ws.backpack.exchange"
DEFAULT_TIME_IN_FORCE = "GTC"

ORDER_ID_MAX_LEN = None
HBOT_ORDER_ID_PREFIX = ""

# WebSocket endpoints
WSS_PUBLIC_ENDPOINT = "/"
WSS_PRIVATE_ENDPOINT = "/"

MARGIN_MODE_TYPES = {
    MarginMode.CROSS: "cross",
    MarginMode.ISOLATED: "isolated",
}
ORDER_TYPES = {
    OrderType.LIMIT: "Limit",
    OrderType.MARKET: "Market",
}
POSITION_MODE_TYPES = {
    PositionMode.ONEWAY: "one_way",
    PositionMode.HEDGE: "hedge",
}
STATE_TYPES = {
    "New": OrderState.OPEN,
    "Filled": OrderState.FILLED,
    "PartiallyFilled": OrderState.PARTIALLY_FILLED,
    "Cancelled": OrderState.CANCELED,
    "Canceled": OrderState.CANCELED,
    "Expired": OrderState.CANCELED,
}

SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 20
WS_HEARTBEAT_TIME_INTERVAL = 30

# Product types for Backpack
PERP_PRODUCT_TYPE = "PERP"

# Public endpoints
PUBLIC_MARKETS_ENDPOINT = "/api/v1/markets"
PUBLIC_TICKER_ENDPOINT = "/api/v1/ticker"
PUBLIC_ORDERBOOK_ENDPOINT = "/api/v1/depth"
PUBLIC_TRADES_ENDPOINT = "/api/v1/trades"
PUBLIC_KLINES_ENDPOINT = "/api/v1/klines"
PUBLIC_TIME_ENDPOINT = "/api/v1/time"
PUBLIC_STATUS_ENDPOINT = "/api/v1/status"

# Private endpoints - Trading
PLACE_ORDER_ENDPOINT = "/api/v1/order"
CANCEL_ORDER_ENDPOINT = "/api/v1/order"
GET_ORDER_ENDPOINT = "/api/v1/order"
GET_OPEN_ORDERS_ENDPOINT = "/api/v1/orders"
BATCH_ORDERS_ENDPOINT = "/api/v1/orders"

# Private endpoints - Account
ACCOUNT_ENDPOINT = "/api/v1/account"
CAPITAL_ENDPOINT = "/api/v1/capital"
POSITION_ENDPOINT = "/api/v1/position"

# Private endpoints - History (wapi)
ORDER_HISTORY_ENDPOINT = "/wapi/v1/history/orders"
FILL_HISTORY_ENDPOINT = "/wapi/v1/history/fills"
POSITION_HISTORY_ENDPOINT = "/wapi/v1/history/position"
FUNDING_HISTORY_ENDPOINT = "/wapi/v1/history/funding"
PNL_HISTORY_ENDPOINT = "/wapi/v1/history/pnl"

# WebSocket channels
PUBLIC_WS_BOOKS = "depth"
PUBLIC_WS_TRADE = "trade"
PUBLIC_WS_TICKER = "ticker"

PUBLIC_WS_PING_REQUEST = "ping"
PUBLIC_WS_PONG_RESPONSE = "pong"

WS_POSITIONS_ENDPOINT = "position"
WS_ORDERS_ENDPOINT = "order"
WS_ACCOUNT_ENDPOINT = "account"

# Response codes
RET_CODE_OK = "success"

RATE_LIMITS = [
    RateLimit(limit_id=PUBLIC_MARKETS_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=PUBLIC_TICKER_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=PUBLIC_ORDERBOOK_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=PUBLIC_TRADES_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=PUBLIC_TIME_ENDPOINT, limit=10, time_interval=1),

    RateLimit(limit_id=PLACE_ORDER_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=CANCEL_ORDER_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=GET_ORDER_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=GET_OPEN_ORDERS_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=ACCOUNT_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=CAPITAL_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=POSITION_ENDPOINT, limit=10, time_interval=1),
]
