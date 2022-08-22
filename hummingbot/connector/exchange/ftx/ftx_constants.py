import sys

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

HBOT_BROKER_ID = "hummingbot1"
MAX_ORDER_ID_LEN = None

DEFAULT_DOMAIN = ""
FTX_BASE_URL = "https://ftx.com/api"
FTX_WS_URL = "wss://ftx.com/ws"

# Public endpoints
FTX_NETWORK_STATUS_PATH = ""
FTX_ORDER_BOOK_PATH = "/markets/{}/orderbook"
FTX_MARKETS_PATH = "/markets"
FTX_SINGLE_MARKET_PATH = "/markets/{}"

# Private endpoints (require authentication)
FTX_PLACE_ORDER_PATH = "/orders"
FTX_ORDER_WITH_CLIENT_ID_PATH = "/orders/by_client_id/{}"
FTX_ORDER_FILLS_PATH = "/fills"
FTX_BALANCES_PATH = "/wallet/balances"

WS_PING_INTERVAL = 15
WS_TRADES_CHANNEL = "trades"
WS_ORDER_BOOK_CHANNEL = "orderbook"
WS_PRIVATE_FILLS_CHANNEL = "fills"
WS_PRIVATE_ORDERS_CHANNEL = "orders"

WS_EVENT_UPDATE_TYPE = "update"
WS_EVENT_ERROR_TYPE = "error"
WS_EVENT_ERROR_CODE = 400
WS_EVENT_NOT_LOGGED_IN_MESSAGE = "Not logged in"
WS_EVENT_INVALID_LOGIN_MESSAGE = "Invalid login credentials"

NO_LIMIT = sys.maxsize
# FTX_NETWORK_STATUS_LIMIT_ID = "FTXNetworkStatusHTTPRequest"
FTX_ORDER_BOOK_LIMIT_ID = "FTXOrderBookHTTPRequest"
FTX_GET_ORDER_LIMIT_ID = "FTXGetOrderHTTPRequest"
FTX_CANCEL_ORDER_LIMIT_ID = "FTXCancelOrderHTTPRequest"
WS_CONNECTION_LIMIT_ID = "FTXWSConnection"
WS_REQUEST_LIMIT_ID = "FTXWSRequest"
FTX_PER_SECOND_ORDER_SPOT_LIMIT_ID = "FTXPerSecondOrderSpot"
FTX_PER_MS_ORDER_SPOT_LIMIT_ID = "FTXPerMSOrderSpot"
# The limits are configured considering Tiers 1-5 defaults. They have to be changed for other tiers according to
# https://help.ftx.com/hc/en-us/articles/360052595091-2020-11-20-Ratelimit-Updates
PER_SECOND_SPOT_LIMIT = 7
PER_200_MS_SPOT_LIMIT = 2

TWO_HUNDRED_MS = 200 / 1000

RATE_LIMITS = [
    RateLimit(WS_CONNECTION_LIMIT_ID, limit=NO_LIMIT, time_interval=1),
    RateLimit(WS_REQUEST_LIMIT_ID, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=FTX_PER_SECOND_ORDER_SPOT_LIMIT_ID, limit=PER_SECOND_SPOT_LIMIT, time_interval=1),
    RateLimit(limit_id=FTX_PER_MS_ORDER_SPOT_LIMIT_ID, limit=PER_200_MS_SPOT_LIMIT, time_interval=TWO_HUNDRED_MS),
    RateLimit(limit_id=FTX_NETWORK_STATUS_PATH, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=FTX_ORDER_BOOK_LIMIT_ID, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=FTX_MARKETS_PATH, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=FTX_PLACE_ORDER_PATH, limit=NO_LIMIT, time_interval=1, linked_limits=[
        LinkedLimitWeightPair(limit_id=FTX_PER_SECOND_ORDER_SPOT_LIMIT_ID),
        LinkedLimitWeightPair(limit_id=FTX_PER_MS_ORDER_SPOT_LIMIT_ID),
    ]),
    RateLimit(limit_id=FTX_CANCEL_ORDER_LIMIT_ID, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=FTX_GET_ORDER_LIMIT_ID, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=FTX_ORDER_FILLS_PATH, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=FTX_BALANCES_PATH, limit=NO_LIMIT, time_interval=1),
]
