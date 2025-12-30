from enum import Enum

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionMode
from hummingbot.core.data_type.in_flight_order import OrderState


class MarginMode(Enum):
    CROSS = "CROSS"
    ISOLATED = "ISOLATED"


EXCHANGE_NAME = "backpack_perpetual"

# Backpack Exchange API - https://docs.backpack.exchange/
REST_URL = "https://api.backpack.exchange"
WSS_URL = "wss://ws.backpack.exchange"

DEFAULT_DOMAIN = "api.backpack.exchange"
DEFAULT_TIME_IN_FORCE = "GTC"

ORDER_ID_MAX_LEN = None
HBOT_ORDER_ID_PREFIX = "hbot"

# WebSocket endpoints
WSS_PUBLIC_ENDPOINT = "/"
WSS_PRIVATE_ENDPOINT = "/"

MARGIN_MODE_TYPES = {
    MarginMode.CROSS: "CROSS",
    MarginMode.ISOLATED: "ISOLATED",
}

ORDER_TYPES = {
    OrderType.LIMIT: "Limit",
    OrderType.MARKET: "Market",
}

POSITION_MODE_TYPES = {
    PositionMode.ONEWAY: "OneWay",
    PositionMode.HEDGE: "BothSide",
}

STATE_TYPES = {
    "New": OrderState.OPEN,
    "Filled": OrderState.FILLED,
    "PartiallyFilled": OrderState.PARTIALLY_FILLED,
    "Cancelled": OrderState.CANCELED,
    "Expired": OrderState.CANCELED,
    "Triggered": OrderState.OPEN,
}

SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 20
WS_HEARTBEAT_TIME_INTERVAL = 30

# Product types for perpetuals
USDC_PRODUCT_TYPE = "PERP"

# =============================================================================
# REST API Endpoints (Backpack Exchange v1 API)
# Docs: https://docs.backpack.exchange/
# =============================================================================

# Public endpoints (no auth required)
PUBLIC_TICKER_ENDPOINT = "/api/v1/ticker"
PUBLIC_TICKERS_ENDPOINT = "/api/v1/tickers"
PUBLIC_DEPTH_ENDPOINT = "/api/v1/depth"
PUBLIC_KLINES_ENDPOINT = "/api/v1/klines"
PUBLIC_TRADES_ENDPOINT = "/api/v1/trades"
PUBLIC_MARKETS_ENDPOINT = "/api/v1/markets"
PUBLIC_ASSETS_ENDPOINT = "/api/v1/assets"
PUBLIC_TIME_ENDPOINT = "/api/v1/time"
PUBLIC_STATUS_ENDPOINT = "/api/v1/status"

# Private endpoints (require ED25519 signature)
ACCOUNT_BALANCE_ENDPOINT = "/api/v1/capital"
PLACE_ORDER_ENDPOINT = "/api/v1/order"
CANCEL_ORDER_ENDPOINT = "/api/v1/order"
GET_ORDER_ENDPOINT = "/api/v1/order"
GET_ORDERS_ENDPOINT = "/api/v1/orders"
ORDER_HISTORY_ENDPOINT = "/api/v1/history/orders"
FILL_HISTORY_ENDPOINT = "/api/v1/history/fills"
POSITION_ENDPOINT = "/api/v1/position"
SET_LEVERAGE_ENDPOINT = "/wapi/v1/leverage"

# Instruction types for ED25519 signing
INSTRUCTION_BALANCE_QUERY = "balanceQuery"
INSTRUCTION_ORDER_EXECUTE = "orderExecute"
INSTRUCTION_ORDER_CANCEL = "orderCancel"
INSTRUCTION_ORDER_QUERY = "orderQuery"
INSTRUCTION_ORDER_QUERY_ALL = "orderQueryAll"
INSTRUCTION_POSITION_QUERY = "positionQuery"

# WebSocket channels
WS_CHANNEL_ORDERBOOK = "depth"
WS_CHANNEL_TRADES = "trades"
WS_CHANNEL_TICKER = "ticker"
WS_CHANNEL_ACCOUNT = "account"
WS_CHANNEL_ORDERS = "orders"
WS_CHANNEL_POSITIONS = "positions"

RET_CODE_OK = "OK"

# Rate limits
RATE_LIMITS = [
    RateLimit(limit_id=PUBLIC_TICKER_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=PUBLIC_TICKERS_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=PUBLIC_DEPTH_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=PUBLIC_MARKETS_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=PUBLIC_TIME_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=ACCOUNT_BALANCE_ENDPOINT, limit=5, time_interval=1),
    RateLimit(limit_id=PLACE_ORDER_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=CANCEL_ORDER_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=GET_ORDERS_ENDPOINT, limit=5, time_interval=1),
    RateLimit(limit_id=POSITION_ENDPOINT, limit=5, time_interval=1),
    RateLimit(limit_id=SET_LEVERAGE_ENDPOINT, limit=5, time_interval=1),
]
