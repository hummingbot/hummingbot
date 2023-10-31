from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "main"
REST_URLS = {"main": "https://open-api.bingx.com"}

WSS_PRIVATE_URL = {"main": "wss://open-api-ws.bingx.com/market"}

# Websocket event types
DIFF_EVENT_TYPE = ""
TRADE_EVENT_TYPE = ""
SNAPSHOT_EVENT_TYPE = "depth"

# Public API endpoints
LAST_TRADED_PRICE_PATH = "/openApi/spot/v1/ticker/24hr"
EXCHANGE_INFO_PATH_URL = "/openApi/spot/v1/common/symbols"
SNAPSHOT_PATH_URL = "/openApi/spot/v1/market/depth"
SERVER_TIME_PATH_URL = "/openApi/swap/v2/server/time"

# Private API endpoints
ACCOUNTS_PATH_URL = "/openApi/spot/v1/account/balance"
MY_TRADES_PATH_URL = ""
ORDER_PATH_URL = ""


# Rate Limit Type
REQUEST_GET = "GET"
REQUEST_GET_BURST = "GET_BURST"
REQUEST_GET_MIXED = "GET_MIXED"
REQUEST_POST = "POST"
REQUEST_POST_BURST = "POST_BURST"
REQUEST_POST_MIXED = "POST_MIXED"

# Rate Limit Max request

MAX_REQUEST_GET = 6000
MAX_REQUEST_GET_BURST = 70
MAX_REQUEST_GET_MIXED = 400
MAX_REQUEST_POST = 2400
MAX_REQUEST_POST_BURST = 50
MAX_REQUEST_POST_MIXED = 270

# Rate Limit time intervals
TWO_MINUTES = 120
ONE_SECOND = 1
SIX_SECONDS = 6
ONE_DAY = 86400

RATE_LIMITS = {
    # General
    RateLimit(limit_id=REQUEST_GET, limit=MAX_REQUEST_GET, time_interval=TWO_MINUTES),
    RateLimit(limit_id=REQUEST_GET_BURST, limit=MAX_REQUEST_GET_BURST, time_interval=ONE_SECOND),
    RateLimit(limit_id=REQUEST_GET_MIXED, limit=MAX_REQUEST_GET_MIXED, time_interval=SIX_SECONDS),
    RateLimit(limit_id=REQUEST_POST, limit=MAX_REQUEST_POST, time_interval=TWO_MINUTES),
    RateLimit(limit_id=REQUEST_POST_BURST, limit=MAX_REQUEST_POST_BURST, time_interval=ONE_SECOND),
    RateLimit(limit_id=REQUEST_POST_MIXED, limit=MAX_REQUEST_POST_MIXED, time_interval=SIX_SECONDS),
    # Linked limits
    RateLimit(limit_id=LAST_TRADED_PRICE_PATH, limit=MAX_REQUEST_GET, time_interval=TWO_MINUTES,
              linked_limits=[LinkedLimitWeightPair(REQUEST_GET, 1), LinkedLimitWeightPair(REQUEST_GET_BURST, 1),
                             LinkedLimitWeightPair(REQUEST_GET_MIXED, 1)]),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=MAX_REQUEST_GET, time_interval=TWO_MINUTES,
              linked_limits=[LinkedLimitWeightPair(REQUEST_GET, 1), LinkedLimitWeightPair(REQUEST_GET_BURST, 1),
                             LinkedLimitWeightPair(REQUEST_GET_MIXED, 1)]),
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=MAX_REQUEST_GET, time_interval=TWO_MINUTES,
              linked_limits=[LinkedLimitWeightPair(REQUEST_GET, 1), LinkedLimitWeightPair(REQUEST_GET_BURST, 1),
                             LinkedLimitWeightPair(REQUEST_GET_MIXED, 1)]),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=MAX_REQUEST_GET, time_interval=TWO_MINUTES,
              linked_limits=[LinkedLimitWeightPair(REQUEST_GET, 1), LinkedLimitWeightPair(REQUEST_GET_BURST, 1),
                             LinkedLimitWeightPair(REQUEST_GET_MIXED, 1)]),
    RateLimit(limit_id=ORDER_PATH_URL, limit=MAX_REQUEST_GET, time_interval=TWO_MINUTES,
              linked_limits=[LinkedLimitWeightPair(REQUEST_POST, 1), LinkedLimitWeightPair(REQUEST_POST_BURST, 1),
                             LinkedLimitWeightPair(REQUEST_POST_MIXED, 1)]),
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=MAX_REQUEST_GET, time_interval=TWO_MINUTES,
              linked_limits=[LinkedLimitWeightPair(REQUEST_POST, 1), LinkedLimitWeightPair(REQUEST_POST_BURST, 1),
                             LinkedLimitWeightPair(REQUEST_POST_MIXED, 1)]),
    RateLimit(limit_id=MY_TRADES_PATH_URL, limit=MAX_REQUEST_GET, time_interval=TWO_MINUTES,
              linked_limits=[LinkedLimitWeightPair(REQUEST_POST, 1), LinkedLimitWeightPair(REQUEST_POST_BURST, 1),
                             LinkedLimitWeightPair(REQUEST_POST_MIXED, 1)]),

}


EXCHANGE_NAME = "bingx"
HBOT_BROKER_ID = "hummingbot"
HBOT_ORDER_ID = "t-HBOT"

REST_URL = "https://open-api.bingx.com/openapi"


SYMBOL_PATH_URL = "/spot/v1/common/symbols"

TRADE_EVENT_TYPE = "trade"
DIFF_EVENT_TYPE = "depthUpdate"

BINGX_USER_STREAM_PATH_URL = "/user/auth/userDataStream"
