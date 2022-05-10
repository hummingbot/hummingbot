import sys

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

CLIENT_ID_PREFIX = "93027a12dac34fBC"
MAX_ID_LEN = 32
SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 30 * 0.8

# URLs

OKEX_BASE_URL = "https://www.okx.com/"

# Doesn't include base URL as the tail is required to generate the signature

OKEX_SERVER_TIME_PATH = '/api/v5/public/time'
OKEX_INSTRUMENTS_PATH = '/api/v5/public/instruments'
OKEX_TICKER_PATH = '/api/v5/market/ticker'
OKEX_ORDER_BOOK_PATH = '/api/v5/market/books'

# Auth required
OKEX_PLACE_ORDER_PATH = "/api/v5/trade/order"
OKEX_ORDER_DETAILS_PATH = '/api/v5/trade/order'
OKEX_ORDER_CANCEL_PATH = '/api/v5/trade/cancel-order'
OKEX_BATCH_ORDER_CANCEL_PATH = '/api/v5/trade/cancel-batch-orders'
OKEX_BALANCE_PATH = '/api/v5/account/balance'
OKEX_TRADE_FILLS_PATH = "/api/v5/trade/fills"

# WS
OKEX_WS_URI_PUBLIC = "wss://ws.okx.com:8443/ws/v5/public"
OKEX_WS_URI_PRIVATE = "wss://ws.okx.com:8443/ws/v5/private"

OKEX_WS_ACCOUNT_CHANNEL = "account"
OKEX_WS_ORDERS_CHANNEL = "orders"
OKEX_WS_PUBLIC_TRADES_CHANNEL = "trades"
OKEX_WS_PUBLIC_BOOKS_CHANNEL = "books"

OKEX_WS_CHANNELS = {
    OKEX_WS_ACCOUNT_CHANNEL,
    OKEX_WS_ORDERS_CHANNEL
}

WS_CONNECTION_LIMIT_ID = "WSConnection"
WS_REQUEST_LIMIT_ID = "WSRequest"
WS_SUBSCRIPTION_LIMIT_ID = "WSSubscription"
WS_LOGIN_LIMIT_ID = "WSLogin"

ORDER_STATE = {
    "live": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "canceled": OrderState.CANCELLED,
}

NO_LIMIT = sys.maxsize

RATE_LIMITS = [
    RateLimit(WS_CONNECTION_LIMIT_ID, limit=1, time_interval=1),
    RateLimit(WS_REQUEST_LIMIT_ID, limit=100, time_interval=10),
    RateLimit(WS_SUBSCRIPTION_LIMIT_ID, limit=240, time_interval=60 * 60),
    RateLimit(WS_LOGIN_LIMIT_ID, limit=1, time_interval=15),
    RateLimit(limit_id=OKEX_SERVER_TIME_PATH, limit=10, time_interval=2),
    RateLimit(limit_id=OKEX_INSTRUMENTS_PATH, limit=20, time_interval=2),
    RateLimit(limit_id=OKEX_TICKER_PATH, limit=20, time_interval=2),
    RateLimit(limit_id=OKEX_ORDER_BOOK_PATH, limit=20, time_interval=2),
    RateLimit(limit_id=OKEX_PLACE_ORDER_PATH, limit=60, time_interval=2),
    RateLimit(limit_id=OKEX_ORDER_DETAILS_PATH, limit=60, time_interval=2),
    RateLimit(limit_id=OKEX_ORDER_CANCEL_PATH, limit=60, time_interval=2),
    RateLimit(limit_id=OKEX_BATCH_ORDER_CANCEL_PATH, limit=300, time_interval=2),
    RateLimit(limit_id=OKEX_BALANCE_PATH, limit=10, time_interval=2),
    RateLimit(limit_id=OKEX_TRADE_FILLS_PATH, limit=60, time_interval=2),
]
