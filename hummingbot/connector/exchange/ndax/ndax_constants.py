# A single source of truth for constant variables related to the exchange

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

# WebSocket Public Endpoints
ACCOUNT_POSITION_EVENT_ENDPOINT_NAME = "AccountPositionEvent"
AUTHENTICATE_USER_ENDPOINT_NAME = "AuthenticateUser"
ORDER_STATE_EVENT_ENDPOINT_NAME = "OrderStateEvent"
ORDER_TRADE_EVENT_ENDPOINT_NAME = "OrderTradeEvent"
SUBSCRIBE_ACCOUNT_EVENTS_ENDPOINT_NAME = "SubscribeAccountEvents"
WS_ORDER_BOOK_CHANNEL = "SubscribeLevel2"
WS_PING_REQUEST = "Ping"

# WebSocket Message Events
WS_ORDER_BOOK_L2_UPDATE_EVENT = "Level2UpdateEvent"

API_LIMIT_REACHED_ERROR_MESSAGE = "TOO MANY REQUESTS"
