from hummingbot.connector.constants import MINUTE, SECOND
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = ""

REST_URL = "https://www.bitstamp.net/api/"
WSS_URL = "wss://ws.bitstamp.net"

API_VERSION = "v2"

MAX_ORDER_ID_LEN = None
HBOT_ORDER_ID_PREFIX = "hbot"

# Order States
ORDER_STATE = {
    "Open": OrderState.OPEN,
    "Finished": OrderState.FILLED,
    "Expired": OrderState.CANCELED,
    "Canceled": OrderState.CANCELED,
}

# Error Codes
ORDER_NOT_EXIST_ERROR_CODE = "404.002"
ORDER_NOT_EXIST_MESSAGE = "Order not found"
TIMESTAMP_ERROR_CODE = "API0017"
TIMESTAMP_ERROR_MESSAGE = "X-Auth-Timestamp header"

SIDE_BUY = "buy"
SIDE_SELL = "sell"

# Public API endpoints
STATUS_URL = "/status/"
CURRENCIES_URL = "/currencies/"
EXCHANGE_INFO_PATH_URL = "/trading-pairs-info/"
ORDER_BOOK_URL = "/order_book/{}"
TICKER_URL = "/ticker/{}"

# Private API endpoints
ACCOUNT_BALANCES_URL = "/account_balances/"
ORDER_CANCEL_URL = "/cancel_order/"
ORDER_STATUS_URL = "/order_status/"
TRADING_FEES_URL = "/fees/trading/"
WEBSOCKET_TOKEN_URL = "/websockets_token/"

# WS Events
DIFF_EVENT_TYPE = "data"
TRADE_EVENT_TYPE = "trade"
USER_ORDER_CREATED = "order_created"
USER_ORDER_CHANGED = "order_changed"
USER_ORDER_DELETED = "order_deleted"
USER_TRADE = "trade"
USER_SELF_TRADE = "self_trade"

# WS Public channels
WS_PUBLIC_DIFF_ORDER_BOOK = "diff_order_book_{}"
WS_PUBLIC_LIVE_TRADES = "live_trades_{}"

# WS Private channels
WS_PRIVATE_MY_ORDERS = "private-my_orders_{}-{}"
WS_PRIVATE_MY_TRADES = "private-my_trades_{}-{}"
WS_PRIVATE_MY_SELF_TRADES = "private-live_trades_{}-{}"

# WS Other
WS_HEARTBEAT_TIME_INTERVAL = 30.0

# Rate Limit
MAX_REQUEST = 10000
MAX_REQUESTS_PER_SECOND = 400

RAW_REQUESTS_LIMIT_ID = "raw_requests"
REQUEST_WEIGHT_LIMIT_ID = "request_weight"
ORDER_BOOK_URL_LIMIT_ID = 'order_book'
ORDER_CREATE_URL_LIMIT_ID = 'order_create'
TICKER_URL_LIMIT_ID = 'ticker'

RATE_LIMITS = [
    RateLimit(limit_id=RAW_REQUESTS_LIMIT_ID, limit=MAX_REQUEST, time_interval=10 * MINUTE),
    RateLimit(limit_id=REQUEST_WEIGHT_LIMIT_ID, limit=MAX_REQUESTS_PER_SECOND, time_interval=SECOND, linked_limits=[LinkedLimitWeightPair(RAW_REQUESTS_LIMIT_ID)]),
    RateLimit(limit_id=STATUS_URL, limit=MAX_REQUESTS_PER_SECOND, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_LIMIT_ID),
                             LinkedLimitWeightPair(RAW_REQUESTS_LIMIT_ID)]),
    RateLimit(limit_id=CURRENCIES_URL, limit=MAX_REQUESTS_PER_SECOND, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_LIMIT_ID),
                             LinkedLimitWeightPair(RAW_REQUESTS_LIMIT_ID)]),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=MAX_REQUESTS_PER_SECOND, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_LIMIT_ID),
                             LinkedLimitWeightPair(RAW_REQUESTS_LIMIT_ID)]),
    RateLimit(limit_id=ORDER_BOOK_URL_LIMIT_ID, limit=MAX_REQUESTS_PER_SECOND, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_LIMIT_ID),
                             LinkedLimitWeightPair(RAW_REQUESTS_LIMIT_ID)]),
    RateLimit(limit_id=TICKER_URL_LIMIT_ID, limit=MAX_REQUESTS_PER_SECOND, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_LIMIT_ID),
                             LinkedLimitWeightPair(RAW_REQUESTS_LIMIT_ID)]),
    RateLimit(limit_id=ACCOUNT_BALANCES_URL, limit=MAX_REQUESTS_PER_SECOND, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_LIMIT_ID),
                             LinkedLimitWeightPair(RAW_REQUESTS_LIMIT_ID)]),
    RateLimit(limit_id=ORDER_CREATE_URL_LIMIT_ID, limit=MAX_REQUESTS_PER_SECOND, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_LIMIT_ID),
                             LinkedLimitWeightPair(RAW_REQUESTS_LIMIT_ID)]),
    RateLimit(limit_id=ORDER_CANCEL_URL, limit=MAX_REQUESTS_PER_SECOND, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_LIMIT_ID),
                             LinkedLimitWeightPair(RAW_REQUESTS_LIMIT_ID)]),
    RateLimit(limit_id=ORDER_STATUS_URL, limit=MAX_REQUESTS_PER_SECOND, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_LIMIT_ID),
                             LinkedLimitWeightPair(RAW_REQUESTS_LIMIT_ID)]),
    RateLimit(limit_id=TRADING_FEES_URL, limit=MAX_REQUESTS_PER_SECOND, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_LIMIT_ID),
                             LinkedLimitWeightPair(RAW_REQUESTS_LIMIT_ID)]),
    RateLimit(limit_id=WEBSOCKET_TOKEN_URL, limit=MAX_REQUESTS_PER_SECOND, time_interval=SECOND,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_LIMIT_ID),
                             LinkedLimitWeightPair(RAW_REQUESTS_LIMIT_ID)]),
]
