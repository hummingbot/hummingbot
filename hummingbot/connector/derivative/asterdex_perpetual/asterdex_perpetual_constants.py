from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "asterdex_perpetual"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = None

MARKET_ORDER_SLIPPAGE = 0.05

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "asterdex_perpetual_testnet"

# AsterDex Perpetual API endpoints - based on official documentation
BASE_URL = "https://fapi.asterdex.com/api/v1"
TESTNET_BASE_URL = "https://fapi.asterdex.com/api/v1"  # Same for now
WS_URL = "wss://fstream.asterdex.com/ws"
TESTNET_WS_URL = "wss://fstream.asterdex.com/ws"

FUNDING_RATE_UPDATE_INTERNAL_SECOND = 60
CURRENCY = "USDT"
META_INFO = "meta"
ASSET_CONTEXT_TYPE_1 = "spotMeta"
ASSET_CONTEXT_TYPE = "spotMetaAndAssetCtxs"
TRADES_TYPE = "userFills"
ORDER_STATUS_TYPE = "orderStatus"
USER_STATE_TYPE = "spotClearinghouseState"

# API Endpoints - AsterDex Futures API v1
TICKER_PRICE_CHANGE_URL = "/ticker/24hr"
SNAPSHOT_REST_URL = "/depth"
EXCHANGE_INFO_URL = "/exchangeInfo"
CANCEL_ORDER_URL = "/order"
CREATE_ORDER_URL = "/order"
ACCOUNT_TRADE_LIST_URL = "/userTrades"
ORDER_URL = "/order"
ACCOUNT_INFO_URL = "/account"
MY_TRADES_PATH_URL = "/userTrades"
PING_URL = "/ping"

TRADES_ENDPOINT_NAME = "trades"
DEPTH_ENDPOINT_NAME = "depth"

USER_ORDERS_ENDPOINT_NAME = "orderUpdates"
USEREVENT_ENDPOINT_NAME = "userFills"

DIFF_EVENT_TYPE = "order_book_snapshot"
TRADE_EVENT_TYPE = "trades"

# Order Statuses
ORDER_STATE = {
    "NEW": OrderState.OPEN,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "FILLED": OrderState.FILLED,
    "CANCELED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.CANCELED,
}

HEARTBEAT_TIME_INTERVAL = 30.0

MAX_REQUEST = 1_200
ALL_ENDPOINTS_LIMIT = "All"

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=MAX_REQUEST, time_interval=60),

    # Weight Limits for individual endpoints
    RateLimit(limit_id=SNAPSHOT_REST_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=TICKER_PRICE_CHANGE_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=EXCHANGE_INFO_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=PING_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=CREATE_ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=CANCEL_ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),

    RateLimit(limit_id=ACCOUNT_TRADE_LIST_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=MY_TRADES_PATH_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ACCOUNT_INFO_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),

]

ORDER_NOT_EXIST_MESSAGE = "order"
UNKNOWN_ORDER_MESSAGE = "Order was never placed, already canceled, or filled"
