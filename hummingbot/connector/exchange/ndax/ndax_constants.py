# A single source of truth for constant variables related to the exchange
from hummingbot.core.api_throttler.data_types import RateLimit, LinkedLimitWeightPair

EXCHANGE_NAME = "ndax"

REST_URLS = {"ndax_main": "https://api.ndax.io:8443/AP/",
             "ndax_testnet": "https://ndaxmarginstaging.cdnhop.net:8443/AP/"}
WSS_URLS = {"ndax_main": "wss://api.ndax.io/WSGateway",
            "ndax_testnet": "wss://ndaxmarginstaging.cdnhop.net/WSGateway"}

REST_API_VERSION = "v3.3"

# REST API Public Endpoints
MARKETS_URL = "GetInstruments"
ORDER_BOOK_URL = "GetL2Snapshot"
LAST_TRADE_PRICE_URL = "GetLevel1"

# REST API Private Endpoints
ACCOUNT_POSITION_PATH_URL = "GetAccountPositions"
USER_ACCOUNT_INFOS_PATH_URL = "GetUserAccountInfos"
SEND_ORDER_PATH_URL = "SendOrder"
CANCEL_ORDER_PATH_URL = "CancelOrder"
GET_ORDER_STATUS_PATH_URL = "GetOrderStatus"
GET_TRADES_HISTORY_PATH_URL = "GetTradesHistory"
GET_OPEN_ORDERS_PATH_URL = "GetOpenOrders"
PING_PATH_URL = "Ping"
HTTP_PING_ID = "HTTPPing"

# WebSocket Public Endpoints
ACCOUNT_POSITION_EVENT_ENDPOINT_NAME = "AccountPositionEvent"
AUTHENTICATE_USER_ENDPOINT_NAME = "AuthenticateUser"
ORDER_STATE_EVENT_ENDPOINT_NAME = "OrderStateEvent"
ORDER_TRADE_EVENT_ENDPOINT_NAME = "OrderTradeEvent"
SUBSCRIBE_ACCOUNT_EVENTS_ENDPOINT_NAME = "SubscribeAccountEvents"
WS_ORDER_BOOK_CHANNEL = "SubscribeLevel2"
WS_PING_REQUEST = "Ping"
WS_PING_ID = "WSPing"

# WebSocket Message Events
WS_ORDER_BOOK_L2_UPDATE_EVENT = "Level2UpdateEvent"

API_LIMIT_REACHED_ERROR_MESSAGE = "TOO MANY REQUESTS"

MINUTE = 60
HTTP_ENDPOINTS_LIMIT_ID = "AllHTTP"
HTTP_LIMIT = 600
WS_AUTH_LIMIT_ID = "AllWsAuth"
WS_ENDPOINTS_LIMIT_ID = "AllWs"
WS_LIMIT = 500
RATE_LIMITS = [
    RateLimit(limit_id=HTTP_ENDPOINTS_LIMIT_ID, limit=HTTP_LIMIT, time_interval=MINUTE),
    # public http
    RateLimit(
        limit_id=MARKETS_URL,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=ORDER_BOOK_URL,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=LAST_TRADE_PRICE_URL,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    # private http
    RateLimit(
        limit_id=ACCOUNT_POSITION_PATH_URL,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=USER_ACCOUNT_INFOS_PATH_URL,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=SEND_ORDER_PATH_URL,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=CANCEL_ORDER_PATH_URL,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=GET_ORDER_STATUS_PATH_URL,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=GET_TRADES_HISTORY_PATH_URL,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=GET_OPEN_ORDERS_PATH_URL,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=HTTP_PING_ID,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    # ws public
    RateLimit(limit_id=WS_AUTH_LIMIT_ID, limit=50, time_interval=MINUTE),
    RateLimit(limit_id=WS_ENDPOINTS_LIMIT_ID, limit=WS_LIMIT, time_interval=MINUTE),
    RateLimit(
        limit_id=ACCOUNT_POSITION_EVENT_ENDPOINT_NAME,
        limit=WS_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(WS_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=AUTHENTICATE_USER_ENDPOINT_NAME,
        limit=50,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(WS_AUTH_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=ORDER_STATE_EVENT_ENDPOINT_NAME,
        limit=WS_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(WS_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=ORDER_TRADE_EVENT_ENDPOINT_NAME,
        limit=WS_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(WS_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=SUBSCRIBE_ACCOUNT_EVENTS_ENDPOINT_NAME,
        limit=WS_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(WS_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=WS_ORDER_BOOK_CHANNEL,
        limit=WS_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(WS_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=WS_PING_ID,
        limit=WS_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(WS_ENDPOINTS_LIMIT_ID)],
    ),
]
