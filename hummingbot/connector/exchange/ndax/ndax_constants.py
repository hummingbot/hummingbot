# A single source of truth for constant variables related to the exchange

EXCHANGE_NAME = "ndax"

# Production URLs
# REST_URL = "https://api.ndax.io:8443/AP/"
# WSS_URL = "wss://api.ndax.io/WSGateway"

# Testing URLs
REST_URL = "https://ndaxmarginstaging.cdnhop.net:8443/AP/"
WSS_URL = "wss://ndaxmarginstaging.cdnhop.net/WSGateway"

REST_API_VERSON = "v3.3"


# REST API Public Endpoints
MARKETS_URL = "GetInstruments"
ORDER_BOOK_URL = "GetL2Snapshot"
LAST_TRADE_PRICE_URL = "GetLevel1"

# REST API Private Endpoints
ACCOUNT_POSITION_PATH_URL = "GetAccountPositions"
USER_ACCOUNTS_PATH_URL = "GetUserAccounts"

# WebSocket Public Endpoints
ACCOUNT_POSITION_EVENT_ENDPOINT_NAME = "AccountPositionEvent"
AUTHENTICATE_USER_ENDPOINT_NAME = "AuthenticateUser"
SUBSCRIBE_ACCOUNT_EVENTS_ENDPOINT_NAME = "SubscribeAccountEvents"
WS_ORDER_BOOK_CHANNEL = "SubscribeLevel2"
WS_PING_REQUEST = "Ping"

# WebSocket Message Events
WS_ORDER_BOOK_L2_UPDATE_EVENT = "Level2UpdateEvent"
