# A single source of truth for constant variables related to the exchange
# https://api.btcmarkets.net/doc/v3#section/General-notes

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "btc_markets"
DEFAULT_DOMAIN = "btc_markets"
# Base URL
REST_URLS = {"btc_markets": "https://api.btcmarkets.net/"}

WSS_V1_PUBLIC_URL = {"btc_markets": "wss://socket.btcmarkets.net/v2"}

WSS_PRIVATE_URL = {"btc_markets": "wss://socket.btcmarkets.net/v2"}

REST_API_VERSION = "v3"
WS_PING_TIMEOUT = 10

HBOT_ORDER_ID_PREFIX = "BTCM-"
MAX_ORDER_ID_LEN = 32
HBOT_BROKER_ID = "Hummingbot"

SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

TIME_IN_FORCE_GTC = "GTC"

# REST API Public Endpoints
ACCOUNTS_URL = f"{REST_API_VERSION}/accounts"
BALANCE_URL = f"{ACCOUNTS_URL}/me/balances"
FEES_URL = f"{ACCOUNTS_URL}/me/trading-fees"
MARKETS_URL = f"{REST_API_VERSION}/markets"
ORDERS_URL = f"{REST_API_VERSION}/orders"
BATCH_ORDERS_URL = f"{REST_API_VERSION}/batchorders"
TRADES_URL = f"{REST_API_VERSION}/trades"
SERVER_TIME_PATH_URL = f"{REST_API_VERSION}/time"

WS_CONNECTION_LIMIT_ID = "WSConnection"
WS_REQUEST_LIMIT_ID = "WSRequest"
WS_SUBSCRIPTION_LIMIT_ID = "WSSubscription"
WS_LOGIN_LIMIT_ID = "WSLogin"

# Websocket event types
TICK = "tick"
DIFF_EVENT_TYPE = "orderbookUpdate"
SNAPSHOT_EVENT_TYPE = "orderbook"
ORDER_CHANGE_EVENT_TYPE = "orderChange"
TRADE_EVENT_TYPE = "trade"
FUND_CHANGE_EVENT_TYPE = "fundChange"
HEARTBEAT = "heartbeat"
ERROR = "error"
SUBSCRIBE = "subscribe"

# Order States
ORDER_STATE = {
    "Accepted": OrderState.APPROVED,
    "Placed": OrderState.OPEN,
    "Partially Matched": OrderState.PARTIALLY_FILLED,
    "Fully Matched": OrderState.FILLED,
    "Partially Cancelled": OrderState.PENDING_CANCEL,
    "Cancelled": OrderState.CANCELED,
    "Failed": OrderState.FAILED,
}

WS_HEARTBEAT_TIME_INTERVAL = 30

RATE_LIMITS = [
    RateLimit(WS_CONNECTION_LIMIT_ID, limit=3, time_interval=10),
    RateLimit(WS_REQUEST_LIMIT_ID, limit=3, time_interval=10),
    RateLimit(WS_SUBSCRIPTION_LIMIT_ID, limit=3, time_interval=10),
    RateLimit(WS_LOGIN_LIMIT_ID, limit=1, time_interval=15),
    RateLimit(limit_id=ACCOUNTS_URL, limit=50, time_interval=10),
    RateLimit(limit_id=BALANCE_URL, limit=50, time_interval=10),
    RateLimit(limit_id=FEES_URL, limit=50, time_interval=10),
    RateLimit(limit_id=MARKETS_URL, limit=150, time_interval=10),
    RateLimit(limit_id=ORDERS_URL, limit=50, time_interval=10),
    RateLimit(limit_id=BATCH_ORDERS_URL, limit=50, time_interval=10),
    RateLimit(limit_id=TRADES_URL, limit=50, time_interval=10),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=50, time_interval=10)
]
"""
Rate Limits - https://api.btcmarkets.net/doc/v3#section/General-Notes
Rate Limits ws - https://docs.btcmarkets.net/v3/#tag/WS_Overview
"""

# Error codes
INVALID_TIME_WINDOW = "InvalidTimeWindow"
INVALID_TIMESTAMP = "InvalidTimestamp"
INVALID_AUTH_TIMESTAMP = "InvalidAuthTimestamp"
INVALID_AUTH_SIGNATURE = "InvalidAuthSignature"
ORDER_NOT_FOUND = "OrderNotFound"
INVALID_ORDERID = "InvalidOrderId"
