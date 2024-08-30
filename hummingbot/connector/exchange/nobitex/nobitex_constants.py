import sys

from hummingbot.core.api_throttler.data_types import RateLimit

MAX_ORDER_ID_LEN = 40
TRADING_FEES_SYMBOL_LIMIT = 10

DEFAULT_DOMAIN = "main"
HB_PARTNER_ID = "Hummingbot"
HB_PARTNER_KEY = "8fb50686-81a8-408a-901c-07c5ac5bd758"

# REST endpoints
BASE_PATH_URL = {
    "main": "https://api.kucoin.com",
    "hft": "https://api.kucoin.com",
}
PUBLIC_WS_DATA_PATH_URL = "/api/v1/bullet-public"
PRIVATE_WS_DATA_PATH_URL = "/api/v1/bullet-private"
TICKER_PRICE_CHANGE_PATH_URL = "/api/v1/market/orderbook/level1"
SNAPSHOT_NO_AUTH_PATH_URL = "/api/v1/market/orderbook/level2_100"
ACCOUNTS_PATH_URL = "/api/v1/accounts"
SERVER_TIME_PATH_URL = "/api/v1/timestamp"
SYMBOLS_PATH_URL = "/api/v2/symbols"
ORDERS_PATH_URL = "/api/v1/orders"
ORDERS_PATH_URL_HFT = "/api/v1/hf/orders"
FEE_PATH_URL = "/api/v1/trade-fees"
ALL_TICKERS_PATH_URL = "/api/v1/market/allTickers"
FILLS_PATH_URL = "/api/v1/fills"
FILLS_PATH_URL_HFT = "/api/v1/hf/fills"
LIMIT_FILLS_PATH_URL = "/api/v1/limit/fills"
ORDER_CLIENT_ORDER_PATH_URL = "/api/v1/order/client-order"

WS_CONNECTION_LIMIT_ID = "WSConnection"
WS_CONNECTION_LIMIT = 30
WS_CONNECTION_TIME_INTERVAL = 60
WS_REQUEST_LIMIT_ID = "WSRequest"
GET_ORDER_LIMIT_ID = "GetOrders"
POST_ORDER_LIMIT_ID = "PostOrder"
DELETE_ORDER_LIMIT_ID = "DeleteOrder"
WS_PING_HEARTBEAT = 10

DIFF_EVENT_TYPE = "trade.l2update"
TRADE_EVENT_TYPE = "trade.l3match"
ORDER_CHANGE_EVENT_TYPE = "orderChange"
BALANCE_EVENT_TYPE = "account.balance"

NO_LIMIT = sys.maxsize
RATE_LIMITS = [
    RateLimit(WS_CONNECTION_LIMIT_ID, limit=WS_CONNECTION_LIMIT, time_interval=WS_CONNECTION_TIME_INTERVAL),
    RateLimit(WS_REQUEST_LIMIT_ID, limit=100, time_interval=10),

    RateLimit(limit_id=PUBLIC_WS_DATA_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=PRIVATE_WS_DATA_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=TICKER_PRICE_CHANGE_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=SYMBOLS_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=SNAPSHOT_NO_AUTH_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=GET_ORDER_LIMIT_ID, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=FEE_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=ALL_TICKERS_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=LIMIT_FILLS_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=ORDER_CLIENT_ORDER_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=POST_ORDER_LIMIT_ID, limit=45, time_interval=3),
    RateLimit(limit_id=DELETE_ORDER_LIMIT_ID, limit=60, time_interval=3),
    RateLimit(limit_id=ORDERS_PATH_URL, limit=45, time_interval=3),
    RateLimit(limit_id=ORDERS_PATH_URL_HFT, limit=45, time_interval=3),
    RateLimit(limit_id=FILLS_PATH_URL, limit=9, time_interval=3),
    RateLimit(limit_id=FILLS_PATH_URL_HFT, limit=9, time_interval=3),
]

RET_CODE_OK = 200000
RET_CODE_ORDER_NOT_EXIST_OR_NOT_ALLOW_TO_CANCEL = 400100
RET_MSG_ORDER_NOT_EXIST_OR_NOT_ALLOW_TO_CANCEL = "order_not_exist_or_not_allow_to_cancel"
RET_CODE_RESOURCE_NOT_FOUND = 404
RET_MSG_RESOURCE_NOT_FOUND = "Not Found"
RET_CODE_AUTH_TIMESTAMP_ERROR = "400002"
RET_MSG_AUTH_TIMESTAMP_ERROR = "KC-API-TIMESTAMP"
