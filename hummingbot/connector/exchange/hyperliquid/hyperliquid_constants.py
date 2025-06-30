from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "hyperliquid"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = None

MARKET_ORDER_SLIPPAGE = 0.05

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "hyperliquid_testnet"

BASE_URL = "https://api.hyperliquid.xyz"
TESTNET_BASE_URL = "https://api.hyperliquid-testnet.xyz"
WS_URL = "wss://api-ui.hyperliquid.xyz/ws"
TESTNET_WS_URL = "wss://api-ui.hyperliquid-testnet.xyz/ws"


FUNDING_RATE_UPDATE_INTERNAL_SECOND = 60
CURRENCY = "USDC"
META_INFO = "meta"
ASSET_CONTEXT_TYPE_1 = "spotMeta"
ASSET_CONTEXT_TYPE = "spotMetaAndAssetCtxs"
TRADES_TYPE = "userFills"
ORDER_STATUS_TYPE = "orderStatus"
USER_STATE_TYPE = "spotClearinghouseState"

# yes
TICKER_PRICE_CHANGE_URL = "/info"
# yes
SNAPSHOT_REST_URL = "/info"
EXCHANGE_INFO_URL = "/info"
CANCEL_ORDER_URL = "/exchange"
CREATE_ORDER_URL = "/exchange"
ACCOUNT_TRADE_LIST_URL = "/info"
ORDER_URL = "/info"
ACCOUNT_INFO_URL = "/info"
POSITION_INFORMATION_URL = "/info"
MY_TRADES_PATH_URL = "/info"
GET_LAST_FUNDING_RATE_PATH_URL = "/info"
PING_URL = "/info"

TRADES_ENDPOINT_NAME = "trades"
DEPTH_ENDPOINT_NAME = "l2Book"


USER_ORDERS_ENDPOINT_NAME = "orderUpdates"
USEREVENT_ENDPOINT_NAME = "user"

DIFF_EVENT_TYPE = "order_book_snapshot"
TRADE_EVENT_TYPE = "trades"

# Order Statuses
ORDER_STATE = {
    "open": OrderState.OPEN,
    "resting": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "canceled": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
    "reduceOnlyCanceled": OrderState.CANCELED,
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
    RateLimit(limit_id=POSITION_INFORMATION_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=GET_LAST_FUNDING_RATE_PATH_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),

]
ORDER_NOT_EXIST_MESSAGE = "order"
UNKNOWN_ORDER_MESSAGE = "Order was never placed, already canceled, or filled"
