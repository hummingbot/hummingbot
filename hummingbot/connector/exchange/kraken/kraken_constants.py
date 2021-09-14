from hummingbot.core.api_throttler.data_types import RateLimit, \
    LinkedLimitWeightPair

KRAKEN_TO_HB_MAP = {
    "XBT": "BTC",
    "XDG": "DOGE",
}

BASE_URL = "https://api.kraken.com/0"
TICKER_PATH_URL = "/public/Ticker"
SNAPSHOT_PATH_URL = "/public/Depth"
ASSET_PAIRS_PATH_URL = "/public/AssetPairs"
TIME_PATH_URL = "/public/Time"
GET_TOKEN_PATH_URL = "/private/GetWebSocketsToken"
ADD_ORDER_PATH_URL = "/private/AddOrder"
CANCEL_ORDER_PATH_URL = "/private/CancelOrder"
BALANCE_PATH_URL = "/private/Balance"
OPEN_ORDERS_PATH_URL = "/private/OpenOrders"
QUERY_ORDERS_PATH_URL = "/private/QueryOrders"

WS_URL = "wss://ws.kraken.com"
WS_AUTH_URL = "wss://ws-auth.kraken.com/"

GLOBAL_REST_LIMIT_ID = "GlobalRESTLimitID"
REQ_LIMIT = 20
REQ_LIMIT_INTERVAL = 60
WS_CONNECTION_LIMIT_ID = "WSConnectionLimitID"
RATE_LIMITS = [
    RateLimit(limit_id=GLOBAL_REST_LIMIT_ID, limit=REQ_LIMIT, time_interval=REQ_LIMIT_INTERVAL),
    RateLimit(
        limit_id=TICKER_PATH_URL,
        limit=REQ_LIMIT,
        time_interval=REQ_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(GLOBAL_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=SNAPSHOT_PATH_URL,
        limit=REQ_LIMIT,
        time_interval=REQ_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(GLOBAL_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=ASSET_PAIRS_PATH_URL,
        limit=REQ_LIMIT,
        time_interval=REQ_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(GLOBAL_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=GET_TOKEN_PATH_URL,
        limit=REQ_LIMIT,
        time_interval=REQ_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(GLOBAL_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=TIME_PATH_URL,
        limit=REQ_LIMIT,
        time_interval=REQ_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(GLOBAL_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=ADD_ORDER_PATH_URL,
        limit=REQ_LIMIT,
        time_interval=REQ_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(GLOBAL_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=CANCEL_ORDER_PATH_URL,
        limit=REQ_LIMIT,
        time_interval=REQ_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(GLOBAL_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=BALANCE_PATH_URL,
        limit=REQ_LIMIT,
        time_interval=REQ_LIMIT_INTERVAL,
        weight=2,
        linked_limits=[LinkedLimitWeightPair(GLOBAL_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=OPEN_ORDERS_PATH_URL,
        limit=REQ_LIMIT,
        time_interval=REQ_LIMIT_INTERVAL,
        weight=2,
        linked_limits=[LinkedLimitWeightPair(GLOBAL_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=QUERY_ORDERS_PATH_URL,
        limit=REQ_LIMIT,
        time_interval=REQ_LIMIT_INTERVAL,
        weight=2,
        linked_limits=[LinkedLimitWeightPair(GLOBAL_REST_LIMIT_ID)],
    ),
    RateLimit(limit_id=WS_CONNECTION_LIMIT_ID, limit=150, time_interval=60 * 10),
]
