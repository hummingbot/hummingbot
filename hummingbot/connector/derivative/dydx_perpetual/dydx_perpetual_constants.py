from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import OrderState

# A single source of truth for constant variables related to the exchange

EXCHANGE_NAME = "dydx_perpetual"
DEFAULT_DOMAIN = "com"

API_VERSION = "v3"

HBOT_BROKER_ID = "Hummingbot"
MAX_ID_LEN = 40
HEARTBEAT_INTERVAL = 30.0
ORDER_EXPIRATION = 600
LIMIT_FEE = 0.015

# API Base URLs
DYDX_REST_BASE_URL = "https://api.dydx.exchange"
DYDX_REST_URL = "{}/{}".format(DYDX_REST_BASE_URL, API_VERSION)
DYDX_WS_URL = "wss://api.dydx.exchange/{}/ws".format(API_VERSION)

# Public REST Endpoints

PATH_MARKETS = "/markets"
PATH_TICKER = "/stats"
PATH_SNAPSHOT = "/orderbook"
PATH_TIME = "/time"
PATH_ORDERS = "/orders"
PATH_ACTIVE_ORDERS = "/active-orders"
PATH_FILLS = "/fills"

PATH_ACCOUNTS = "/accounts"
PATH_CONFIG = "/config"
PATH_FUNDING = "/funding"


# WS Endpoints
WS_PATH_ACCOUNTS = "/ws/accounts"

# WS Channels
WS_CHANNEL_TRADES = "v3_trades"
WS_CHANNEL_ORDERBOOK = "v3_orderbook"
WS_CHANNEL_MARKETS = "v3_markets"
WS_CHANNEL_ACCOUNTS = "v3_accounts"

WS_TYPE_SUBSCRIBE = "subscribe"
WS_TYPE_SUBSCRIBED = "subscribed"
WS_TYPE_CHANNEL_DATA = "channel_data"


TIF_GOOD_TIL_TIME = "GTT"
TIF_FILL_OR_KILL = "FOK"
TIF_IMMEDIATE_OR_CANCEL = "IOC"
FEES_KEY = "*"
FEE_MAKER_KEY = "maker"
FEE_TAKER_KEY = "taker"

ORDER_TYPE_MAP = {
    OrderType.LIMIT: "LIMIT",
    OrderType.LIMIT_MAKER: "LIMIT",
}

ORDER_STATE = {
    "PENDING": OrderState.OPEN,
    "OPEN": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "CANCELED": OrderState.CANCELED,
}

WS_CHANNEL_TO_PATH = {WS_CHANNEL_ACCOUNTS: WS_PATH_ACCOUNTS}


ERR_MSG_NO_ORDER_FOUND = "No order found with id"
ERR_MSG_NO_ORDER_FOR_MARKET = "No order for market"

LAST_FEE_PAYMENTS_MAX = 1
LAST_FILLS_MAX = 100


ONE_SECOND = 1

LIMIT_ID_GET = "LIMIT_ID_GET"
LIMIT_ID_ORDER_CANCEL = "LIMIT_ID_ORDER_CANCEL"
LIMIT_ID_ORDERS_CANCEL = "LIMIT_ID_ORDERS_CANCEL"
LIMIT_ID_ORDER_PLACE = "LIMIT_ID_ORDER_PLACE"

MAX_REQUESTS_GET = 175

RATE_LIMITS = [
    # Pools
    RateLimit(limit_id=LIMIT_ID_GET, limit=MAX_REQUESTS_GET, time_interval=ONE_SECOND * 10),
    # Weighted limits
    RateLimit(
        limit_id=PATH_CONFIG,
        limit=MAX_REQUESTS_GET,
        time_interval=ONE_SECOND * 10,
        linked_limits=[LinkedLimitWeightPair(LIMIT_ID_GET, 1)],
    ),
    RateLimit(
        limit_id=PATH_FILLS,
        limit=MAX_REQUESTS_GET,
        time_interval=ONE_SECOND * 10,
        linked_limits=[LinkedLimitWeightPair(LIMIT_ID_GET, 1)],
    ),
    RateLimit(
        limit_id=PATH_ORDERS,
        limit=MAX_REQUESTS_GET,
        time_interval=ONE_SECOND * 10,
        linked_limits=[LinkedLimitWeightPair(LIMIT_ID_GET, 1)],
    ),
    RateLimit(
        limit_id=PATH_FUNDING,
        limit=MAX_REQUESTS_GET,
        time_interval=ONE_SECOND * 10,
        linked_limits=[LinkedLimitWeightPair(LIMIT_ID_GET, 1)],
    ),
    RateLimit(
        limit_id=PATH_ACCOUNTS,
        limit=MAX_REQUESTS_GET,
        time_interval=ONE_SECOND * 10,
        linked_limits=[LinkedLimitWeightPair(LIMIT_ID_GET, 1)],
    ),
    RateLimit(
        limit_id=PATH_MARKETS,
        limit=MAX_REQUESTS_GET,
        time_interval=ONE_SECOND * 10,
        linked_limits=[LinkedLimitWeightPair(LIMIT_ID_GET, 1)],
    ),
    RateLimit(
        limit_id=PATH_TIME,
        limit=MAX_REQUESTS_GET,
        time_interval=ONE_SECOND * 10,
        linked_limits=[LinkedLimitWeightPair(LIMIT_ID_GET, 1)],
    ),
    RateLimit(
        limit_id=PATH_SNAPSHOT,
        limit=MAX_REQUESTS_GET,
        time_interval=ONE_SECOND * 10,
        linked_limits=[LinkedLimitWeightPair(LIMIT_ID_GET, 1)],
    ),
]
