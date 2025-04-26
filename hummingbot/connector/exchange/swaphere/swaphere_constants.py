import sys

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import OrderState

CLIENT_ID_PREFIX = "hb_swaphere_"
MAX_ID_LEN = 32
SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 30 * 0.8

DEFAULT_DOMAIN = ""

# URLs
SWAPHERE_BASE_URL = "https://api.swaphere.com/"  # Replace with your actual domain

# API Endpoints
SWAPHERE_SERVER_TIME_PATH = '/api/v2/public/time'
SWAPHERE_INSTRUMENTS_PATH = '/api/v2/public/instruments'
SWAPHERE_TICKER_PATH = '/api/v2/market/ticker'
SWAPHERE_TICKERS_PATH = '/api/v2/market/tickers'
SWAPHERE_ORDER_BOOK_PATH = '/api/v2/market/books'
SWAPHERE_TRADES_PATH = '/api/v2/market/trades'

# Auth required
SWAPHERE_PLACE_ORDER_PATH = "/api/v2/trade/order"
SWAPHERE_ORDER_DETAILS_PATH = '/api/v2/trade/order'
SWAPHERE_ORDER_CANCEL_PATH = '/api/v2/trade/cancel-order'
SWAPHERE_BATCH_ORDER_CANCEL_PATH = '/api/v2/trade/cancel-batch-orders'
SWAPHERE_BALANCE_PATH = '/api/v2/account/balance'
SWAPHERE_TRADE_FILLS_PATH = "/api/v2/trade/fills"

# WS
SWAPHERE_WS_URI_PUBLIC = "wss://ws.swaphere.com:8443/ws/v2/public"
SWAPHERE_WS_URI_PRIVATE = "wss://ws.swaphere.com:8443/ws/v2/private"

SWAPHERE_WS_ACCOUNT_CHANNEL = "account"
SWAPHERE_WS_ORDERS_CHANNEL = "orders"
SWAPHERE_WS_PUBLIC_TRADES_CHANNEL = "trades"
SWAPHERE_WS_PUBLIC_BOOKS_CHANNEL = "books"

SWAPHERE_WS_CHANNELS = {
    SWAPHERE_WS_ACCOUNT_CHANNEL,
    SWAPHERE_WS_ORDERS_CHANNEL
}

WS_CONNECTION_LIMIT_ID = "WSConnection"
WS_REQUEST_LIMIT_ID = "WSRequest"
WS_SUBSCRIPTION_LIMIT_ID = "WSSubscription"
WS_LOGIN_LIMIT_ID = "WSLogin"

ORDER_STATE = {
    "live": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "canceled": OrderState.CANCELED,
}

ORDER_TYPE_MAP = {
    OrderType.LIMIT: "limit",
    OrderType.MARKET: "market",
    OrderType.LIMIT_MAKER: "post_only",
}

NO_LIMIT = sys.maxsize

RATE_LIMITS = [
    RateLimit(WS_CONNECTION_LIMIT_ID, limit=3, time_interval=1),
    RateLimit(WS_REQUEST_LIMIT_ID, limit=100, time_interval=10),
    RateLimit(WS_SUBSCRIPTION_LIMIT_ID, limit=240, time_interval=60 * 60),
    RateLimit(WS_LOGIN_LIMIT_ID, limit=1, time_interval=15),
    RateLimit(limit_id=SWAPHERE_SERVER_TIME_PATH, limit=10, time_interval=2),
    RateLimit(limit_id=SWAPHERE_INSTRUMENTS_PATH, limit=20, time_interval=2),
    RateLimit(limit_id=SWAPHERE_TICKER_PATH, limit=20, time_interval=2),
    RateLimit(limit_id=SWAPHERE_TICKERS_PATH, limit=20, time_interval=2),
    RateLimit(limit_id=SWAPHERE_ORDER_BOOK_PATH, limit=20, time_interval=2),
    RateLimit(limit_id=SWAPHERE_PLACE_ORDER_PATH, limit=20, time_interval=2),
    RateLimit(limit_id=SWAPHERE_ORDER_DETAILS_PATH, limit=20, time_interval=2),
    RateLimit(limit_id=SWAPHERE_ORDER_CANCEL_PATH, limit=20, time_interval=2),
    RateLimit(limit_id=SWAPHERE_BATCH_ORDER_CANCEL_PATH, limit=300, time_interval=2),
    RateLimit(limit_id=SWAPHERE_BALANCE_PATH, limit=10, time_interval=2),
    RateLimit(limit_id=SWAPHERE_TRADE_FILLS_PATH, limit=60, time_interval=2),
] 