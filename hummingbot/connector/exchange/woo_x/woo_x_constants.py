from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "woo_x"

MAX_ORDER_ID_LEN = 19

HBOT_ORDER_ID_PREFIX = ""

REST_URLS = {
    "woo_x": "https://api.woo.org",
    "woo_x_testnet": "https://api.staging.woo.org",
}

WSS_PUBLIC_URLS = {
    "woo_x": "wss://wss.woo.org/ws/stream/{}",
    "woo_x_testnet": "wss://wss.staging.woo.org/ws/stream/{}"
}

WSS_PRIVATE_URLS = {
    "woo_x": "wss://wss.woo.org/v2/ws/private/stream/{}",
    "woo_x_testnet": "wss://wss.staging.woo.org/v2/ws/private/stream/{}"
}

WS_HEARTBEAT_TIME_INTERVAL = 30

EXCHANGE_INFO_PATH_URL = '/v1/public/info'
MARKET_TRADES_PATH = '/v1/public/market_trades'
ORDERBOOK_SNAPSHOT_PATH_URL = '/v1/public/orderbook'
ORDER_PATH_URL = '/v1/order'
CANCEL_ORDER_PATH_URL = '/v1/client/order'
ACCOUNTS_PATH_URL = '/v2/client/holding'
GET_TRADES_BY_ORDER_ID_PATH = '/v1/order/{}/trades'
GET_ORDER_BY_CLIENT_ORDER_ID_PATH = '/v1/client/order/{}'


RATE_LIMITS = [
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=CANCEL_ORDER_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=GET_TRADES_BY_ORDER_ID_PATH, limit=10, time_interval=1),
    RateLimit(limit_id=MARKET_TRADES_PATH, limit=10, time_interval=1),
    RateLimit(limit_id=ORDERBOOK_SNAPSHOT_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=ORDER_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=GET_ORDER_BY_CLIENT_ORDER_ID_PATH, limit=10, time_interval=1)
]

# Websocket event types
DIFF_EVENT_TYPE = "orderbookupdate"
TRADE_EVENT_TYPE = "trade"

SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 20  # According to the documentation this has to be less than 30 seconds

ORDER_STATE = {
    "NEW": OrderState.OPEN,
    "CANCELLED": OrderState.CANCELED,
    "PARTIAL_FILLED": OrderState.PARTIALLY_FILLED,
    "FILLED": OrderState.FILLED,
    "REJECTED": OrderState.FAILED,
    "INCOMPLETE": OrderState.OPEN,
    "COMPLETED": OrderState.COMPLETED,
}

ORDER_NOT_EXIST_ERROR_CODE = -1006

UNKNOWN_ORDER_ERROR_CODE = -1004

TIME_IN_FORCE_GTC = "GTC"  # Good till cancelled
TIME_IN_FORCE_IOC = "IOC"  # Immediate or cancel
TIME_IN_FORCE_FOK = "FOK"  # Fill or kill
