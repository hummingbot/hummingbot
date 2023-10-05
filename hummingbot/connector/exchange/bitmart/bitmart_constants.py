# A single source of truth for constant variables related to the exchange

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "bitmart"
REST_URL = "https://api-cloud.bitmart.com"
WSS_PUBLIC_URL = "wss://ws-manager-compress.bitmart.com/api?protocol=1.1"
WSS_PRIVATE_URL = "wss://ws-manager-compress.bitmart.com/user?protocol=1.1"
WS_PING_TIMEOUT = 20 * 0.8

DEFAULT_DOMAIN = ""
MAX_ORDER_ID_LEN = 32
HBOT_ORDER_ID_PREFIX = ""
BROKER_ID = "hummingbotfound"

PUBLIC_TRADE_CHANNEL_NAME = "spot/trade"
PUBLIC_DEPTH_CHANNEL_NAME = "spot/depth50"
PRIVATE_ORDER_PROGRESS_CHANNEL_NAME = "spot/user/order"

# REST API ENDPOINTS
CHECK_NETWORK_PATH_URL = "system/service"
GET_TRADING_RULES_PATH_URL = "spot/v1/symbols/details"
GET_LAST_TRADING_PRICES_PATH_URL = "spot/v1/ticker"
GET_ORDER_BOOK_PATH_URL = "spot/v1/symbols/book"
CREATE_ORDER_PATH_URL = "spot/v1/submit_order"
CANCEL_ORDER_PATH_URL = "spot/v2/cancel_order"
GET_ACCOUNT_SUMMARY_PATH_URL = "spot/v1/wallet"
GET_ORDER_DETAIL_PATH_URL = "spot/v2/order_detail"
GET_TRADE_DETAIL_PATH_URL = "spot/v1/trades"
SERVER_TIME_PATH = "system/time"

# WS API ENDPOINTS
WS_CONNECT = "WSConnect"
WS_SUBSCRIBE = "WSSubscribe"

# BitMart has a per method API limit
RATE_LIMITS = [
    RateLimit(limit_id=CHECK_NETWORK_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=GET_TRADING_RULES_PATH_URL, limit=30, time_interval=5),
    RateLimit(limit_id=GET_LAST_TRADING_PRICES_PATH_URL, limit=30, time_interval=5),
    RateLimit(limit_id=GET_ORDER_BOOK_PATH_URL, limit=30, time_interval=5),
    RateLimit(limit_id=CREATE_ORDER_PATH_URL, limit=150, time_interval=5),
    RateLimit(limit_id=CANCEL_ORDER_PATH_URL, limit=150, time_interval=5),
    RateLimit(limit_id=GET_ACCOUNT_SUMMARY_PATH_URL, limit=30, time_interval=5),
    RateLimit(limit_id=GET_ORDER_DETAIL_PATH_URL, limit=150, time_interval=5),
    RateLimit(limit_id=GET_TRADE_DETAIL_PATH_URL, limit=30, time_interval=5),
    RateLimit(limit_id=SERVER_TIME_PATH, limit=10, time_interval=1),
    RateLimit(limit_id=WS_CONNECT, limit=30, time_interval=60),
    RateLimit(limit_id=WS_SUBSCRIBE, limit=100, time_interval=10),
]

ORDER_STATE = {
    "1": OrderState.FAILED,
    "2": OrderState.OPEN,
    "3": OrderState.FAILED,
    "4": OrderState.OPEN,
    "5": OrderState.PARTIALLY_FILLED,
    "6": OrderState.FILLED,
    "7": OrderState.PENDING_CANCEL,
    "8": OrderState.CANCELED,
}
