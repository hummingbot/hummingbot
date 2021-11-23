import sys

from hummingbot.core.api_throttler.data_types import RateLimit

# REST endpoints
BASE_PATH_URL = "https://api.kucoin.com"
PUBLIC_WS_DATA_PATH_URL = "/api/v1/bullet-public"
PRIVATE_WS_DATA_PATH_URL = "/api/v1/bullet-private"
TICKER_PRICE_CHANGE_PATH_URL = "/api/v1/market/allTickers"
EXCHANGE_INFO_PATH_URL = "/api/v1/symbols"
SNAPSHOT_PATH_URL = "/api/v3/market/orderbook/level2"
SNAPSHOT_NO_AUTH_PATH_URL = "/api/v1/market/orderbook/level2_100"
ACCOUNTS_PATH_URL = "/api/v1/accounts?type=trade"
SERVER_TIME_PATH_URL = "/api/v1/timestamp"
SYMBOLS_PATH_URL = "/api/v1/symbols"
ORDERS_PATH_URL = "/api/v1/orders"
FEE_PATH_URL = "/api/v1/trade-fees"

TRADE_ORDERS_ENDPOINT_NAME = "/spotMarket/tradeOrders"
BALANCE_ENDPOINT_NAME = "/account/balance"
PRIVATE_ENDPOINT_NAMES = [
    TRADE_ORDERS_ENDPOINT_NAME,
    BALANCE_ENDPOINT_NAME,
]

WS_CONNECTION_LIMIT_ID = "WSConnection"
WS_CONNECTION_LIMIT = 30
WS_CONNECTION_TIME_INTERVAL = 60
WS_REQUEST_LIMIT_ID = "WSRequest"
GET_ORDER_LIMIT_ID = "GetOrders"
POST_ORDER_LIMIT_ID = "PostOrder"
DELETE_ORDER_LIMIT_ID = "DeleteOrder"
FEE_LIMIT_ID = "Fee"
WS_PING_HEARTBEAT = 10

NO_LIMIT = sys.maxsize
RATE_LIMITS = [
    RateLimit(WS_CONNECTION_LIMIT_ID, limit=WS_CONNECTION_LIMIT, time_interval=WS_CONNECTION_TIME_INTERVAL),
    RateLimit(WS_REQUEST_LIMIT_ID, limit=100, time_interval=10),
    RateLimit(limit_id=PUBLIC_WS_DATA_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=PRIVATE_WS_DATA_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=TICKER_PRICE_CHANGE_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=SNAPSHOT_NO_AUTH_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=GET_ORDER_LIMIT_ID, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=FEE_LIMIT_ID, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=POST_ORDER_LIMIT_ID, limit=45, time_interval=3),
    RateLimit(limit_id=DELETE_ORDER_LIMIT_ID, limit=60, time_interval=3),
]
