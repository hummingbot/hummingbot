from os.path import dirname, join, realpath

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = ""

EXCHANGE_NAME = "coinmate"
HBOT_ORDER_ID_PREFIX = "HBOT"
MAX_ORDER_ID_LEN = 64

with open(realpath(join(dirname(__file__), '../../../VERSION'))) as version_file:
    _version = version_file.read().strip()

USER_AGENT = f"Hummingbot/{_version}"

REST_URL = "https://coinmate.io/api"
WSS_URL = "wss://coinmate.io/api/websocket"

TICKER_PATH_URL = "/ticker"
ORDERBOOK_PATH_URL = "/orderBook"
TRANSACTIONS_PATH_URL = "/transactions"
TRADING_PAIRS_PATH_URL = "/tradingPairs"

ACCOUNTS_PATH_URL = "/balances"
OPEN_ORDERS_PATH_URL = "/openOrders"
CANCEL_ORDER_PATH_URL = "/cancelOrder"
TRADER_FEES_PATH_URL = "/traderFees"
BUY_LIMIT_PATH_URL = "/buyLimit"
SELL_LIMIT_PATH_URL = "/sellLimit"
BUY_INSTANT_PATH_URL = "/buyInstant"
SELL_INSTANT_PATH_URL = "/sellInstant"
ORDER_BY_ID_PATH_URL = "/orderById"
MY_TRADES_PATH_URL = "/tradeHistory"
TRADE_HISTORY_PATH_URL = "/tradeHistory"  # Alias for compatibility

SERVER_TIME_PATH_URL = "/system/time"


ORDER_TYPE_LIMIT = "LIMIT"
ORDER_TYPE_INSTANT = "INSTANT"
ORDER_TYPE_QUICK = "QUICK"

ONE_MINUTE = 60

REQUESTS_PER_MINUTE = 100
MAX_REQUEST = 100  # Should match global limit since endpoints are linked

GLOBAL_RATE_LIMIT_ID = "coinmate_global"

DIFF_EVENT_TYPE = "order_book"
TRADE_EVENT_TYPE = "trades"

WS_HEARTBEAT_TIME_INTERVAL = 30.0

# Coinmate rate limiting:
# - Global limit: 100 requests per minute across all endpoints
# - Individual endpoints are linked to the global limit (each counts toward global)
# - WebSocket connections also count toward the global limit
RATE_LIMITS = [
    RateLimit(
        limit_id=GLOBAL_RATE_LIMIT_ID,
        limit=REQUESTS_PER_MINUTE,
        time_interval=ONE_MINUTE
    ),
    *[RateLimit(
        limit_id=path_id,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(GLOBAL_RATE_LIMIT_ID, 1)]
    ) for path_id in [
        TICKER_PATH_URL, ORDERBOOK_PATH_URL, TRANSACTIONS_PATH_URL,
        TRADING_PAIRS_PATH_URL,
        SERVER_TIME_PATH_URL, ACCOUNTS_PATH_URL, BUY_LIMIT_PATH_URL,
        SELL_LIMIT_PATH_URL, BUY_INSTANT_PATH_URL, SELL_INSTANT_PATH_URL,
        CANCEL_ORDER_PATH_URL, OPEN_ORDERS_PATH_URL, MY_TRADES_PATH_URL,
        TRADER_FEES_PATH_URL, ORDER_BY_ID_PATH_URL, WSS_URL
    ]],
]

ORDER_STATE = {
    "OPEN": OrderState.OPEN,
    "CANCELLED": OrderState.CANCELED,
    "FILLED": OrderState.FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "PENDING": OrderState.PENDING_CREATE,
    "REJECTED": OrderState.FAILED,
}

SUPPORTED_QUOTE_CURRENCIES = ["EUR", "CZK"]

ORDER_NOT_EXIST_ERROR_MESSAGE = "Order does not exist"

MAX_RETRIES = 3
INITIAL_BACKOFF_TIME = 1.0
REQUEST_TIMEOUT = 10.0
