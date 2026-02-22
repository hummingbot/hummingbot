from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "main"
EXCHANGE_NAME = "bing_x_perpetual"
HBOT_ORDER_ID_PREFIX = "BXPERP-"
MAX_ORDER_ID_LEN = 40
BROKER_ID = "hummingbot"
SOURCE_KEY = "hummingbot"

SIDE_BUY = "BUY"
SIDE_SELL = "SELL"
POSITION_SIDE_LONG = "LONG"
POSITION_SIDE_SHORT = "SHORT"

TIME_IN_FORCE_GTC = "GTC"
TIME_IN_FORCE_IOC = "IOC"
TIME_IN_FORCE_FOK = "FOK"
TIME_IN_FORCE_POC = "POC"

REST_URLS = {"main": "https://open-api.bingx.com"}
WSS_PUBLIC_URL = {"main": "wss://open-api-ws.bingx.com/market"}
WSS_PRIVATE_URL = {"main": "wss://open-api-ws.bingx.com/market"}

# Public endpoints (perpetual)
LAST_TRADED_PRICE_PATH = "/openApi/swap/v2/quote/ticker"
EXCHANGE_INFO_PATH_URL = "/openApi/swap/v2/quote/contracts"
SNAPSHOT_PATH_URL = "/openApi/swap/v2/quote/depth"
SERVER_TIME_PATH_URL = "/openApi/swap/v2/server/time"
TRADES_PATH_URL = "/openApi/swap/v2/quote/trades"
FUNDING_RATE_PATH_URL = "/openApi/swap/v2/quote/fundingRate"
MARK_PRICE_PATH_URL = "/openApi/swap/v2/quote/premiumIndex"
KLINES_PATH_URL = "/openApi/swap/v3/quote/klines"

# Private endpoints (perpetual)
USER_STREAM_PATH_URL = "/openApi/user/auth/userDataStream"
ACCOUNTS_PATH_URL = "/openApi/swap/v2/user/balance"
POSITIONS_PATH_URL = "/openApi/swap/v2/user/positions"
ORDER_PATH_URL = "/openApi/swap/v2/trade/order"
CANCEL_ORDER_PATH_URL = "/openApi/swap/v2/trade/order"
OPEN_ORDERS_PATH_URL = "/openApi/swap/v2/trade/openOrders"
ALL_ORDERS_PATH_URL = "/openApi/swap/v2/trade/allOrders"
SET_LEVERAGE_PATH_URL = "/openApi/swap/v2/trade/leverage"
ACCOUNT_TRADE_LIST_URL = "/openApi/swap/v2/trade/allFillOrders"
GET_INCOME_HISTORY_URL = "/openApi/swap/v2/user/income"

WS_HEARTBEAT_TIME_INTERVAL = 30

# WebSocket event types
DIFF_EVENT_TYPE = "depth"
TRADE_EVENT_TYPE = "trade"
SNAPSHOT_EVENT_TYPE = "depthSnapshot"

# Order States — map BingX states to HB OrderState
ORDER_STATE = {
    "PENDING": OrderState.PENDING_CREATE,
    "NEW": OrderState.OPEN,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "FILLED": OrderState.FILLED,
    "PENDING_CANCEL": OrderState.PENDING_CANCEL,
    "CANCELED": OrderState.CANCELED,
    "CANCELLED": OrderState.CANCELED,
    "FAILED": OrderState.FAILED,
}

# Position modes
POSITION_MODE_ONEWAY = "one_way"
POSITION_MODE_HEDGE = "hedge"

# Order types
ORDER_TYPE_MARKET = "MARKET"
ORDER_TYPE_LIMIT = "LIMIT"
ORDER_TYPE_STOP_MARKET = "STOP_MARKET"
ORDER_TYPE_TAKE_PROFIT = "TAKE_PROFIT"
ORDER_TYPE_TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"

# Rate limits
REQUEST_GET = "GET"
REQUEST_POST = "POST"
REQUEST_DELETE = "DELETE"

NO_LIMIT = 1000
RATE_LIMITS = [
    RateLimit(limit_id=REQUEST_GET, limit=100, time_interval=1),
    RateLimit(limit_id=REQUEST_POST, limit=100, time_interval=1),
    RateLimit(limit_id=REQUEST_DELETE, limit=100, time_interval=1),
    RateLimit(
        limit_id=LAST_TRADED_PRICE_PATH,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(REQUEST_GET)],
    ),
    RateLimit(
        limit_id=SNAPSHOT_PATH_URL,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(REQUEST_GET)],
    ),
    RateLimit(
        limit_id=EXCHANGE_INFO_PATH_URL,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(REQUEST_GET)],
    ),
    RateLimit(
        limit_id=SERVER_TIME_PATH_URL,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(REQUEST_GET)],
    ),
    RateLimit(
        limit_id=TRADES_PATH_URL,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(REQUEST_GET)],
    ),
    RateLimit(
        limit_id=ORDER_PATH_URL,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(REQUEST_POST)],
    ),
    RateLimit(
        limit_id=CANCEL_ORDER_PATH_URL,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(REQUEST_DELETE)],
    ),
    RateLimit(
        limit_id=ACCOUNTS_PATH_URL,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(REQUEST_GET)],
    ),
    RateLimit(
        limit_id=POSITIONS_PATH_URL,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(REQUEST_GET)],
    ),
    RateLimit(
        limit_id=FUNDING_RATE_PATH_URL,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(REQUEST_GET)],
    ),
    RateLimit(
        limit_id=MARK_PRICE_PATH_URL,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(REQUEST_GET)],
    ),
    RateLimit(
        limit_id=USER_STREAM_PATH_URL,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(REQUEST_POST)],
    ),
    RateLimit(
        limit_id=OPEN_ORDERS_PATH_URL,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(REQUEST_GET)],
    ),
    RateLimit(
        limit_id=ALL_ORDERS_PATH_URL,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(REQUEST_GET)],
    ),
    RateLimit(
        limit_id=SET_LEVERAGE_PATH_URL,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(REQUEST_POST)],
    ),
    RateLimit(
        limit_id=ACCOUNT_TRADE_LIST_URL,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(REQUEST_GET)],
    ),
    RateLimit(
        limit_id=GET_INCOME_HISTORY_URL,
        limit=NO_LIMIT,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(REQUEST_GET)],
    ),
]
