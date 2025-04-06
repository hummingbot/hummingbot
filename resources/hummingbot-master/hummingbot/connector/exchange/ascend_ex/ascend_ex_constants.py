# A single source of truth for constant variables related to the exchange
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

# Max order id allowed by AscendEx is 32. We need to configure it in 22 to unify the timestamp and client_id
# components in the order id, because AscendEx uses the last 9 characters or the order id to generate the
# exchange order id (the last 9 characters would be part of the client id if it is not mixed with the timestamp).
# But AscendEx only uses milliseconds for the timestamp in the exchange order id, causing duplicated exchange order ids
# when running strategies with multi level orders created very fast.
MAX_ORDER_ID_LEN = 22

PING_TIMEOUT = 15.0
DEFAULT_DOMAIN = ""
HBOT_ORDER_ID_PREFIX = "HMBot"

EXCHANGE_NAME = "ascend_ex"
PUBLIC_REST_URL = "https://ascendex.com/api/pro/v1/"
PRIVATE_REST_URL = "https://ascendex.com/{group_id}/api/pro/v1/"
WS_URL = "wss://ascendex.com:443/api/pro/v1/websocket-for-hummingbot-liq-mining"
PRIVATE_WS_URL = "wss://ascendex.com:443/{group_id}/api/pro/v1/websocket-for-hummingbot-liq-mining"

# REST API ENDPOINTS
ORDER_PATH_URL = "cash/order"
ORDER_BATCH_PATH_URL = "cash/order/batch"
ORDER_OPEN_PATH_URL = "cash/order/open"
ORDER_STATUS_PATH_URL = "cash/order/status"
BALANCE_PATH_URL = "cash/balance"
BALANCE_HISTORY_PATH_URL = "data/v1/cash/balance/history"
HIST_PATH_URL = "cash/order/hist/current"
FEE_PATH_URL = "spot/fee"
TICKER_PATH_URL = "spot/ticker"
PRODUCTS_PATH_URL = "cash/products"
TRADES_PATH_URL = "trades"
DEPTH_PATH_URL = "depth"
INFO_PATH_URL = "info"
STREAM_PATH_URL = "stream"

SERVER_LIMIT_INFO = "risk-limit-info"

# WS API ENDPOINTS
SUB_ENDPOINT_NAME = "sub"
PONG_ENDPOINT_NAME = "pong"
TRADE_TOPIC_ID = "trades"
DIFF_TOPIC_ID = "depth"
PING_TOPIC_ID = "ping"
ACCOUNT_TYPE = "CASH"
BALANCE_EVENT_TYPE = "balance"
ORDER_CHANGE_EVENT_TYPE = "order"

# OrderStates

ORDER_STATE = {
    "PendingNew": OrderState.PENDING_CREATE,
    "New": OrderState.OPEN,
    "Filled": OrderState.FILLED,
    "PartiallyFilled": OrderState.PARTIALLY_FILLED,
    "Canceled": OrderState.CANCELED,
    "Rejected": OrderState.FAILED,
}

# AscendEx has multiple pools for API request limits
# Any call increases call rate in ALL pool, so e.g. a cash/order call will contribute to both ALL and cash/order pools.
ALL_ENDPOINTS_LIMIT = "All"
RATE_LIMITS = [
    RateLimit(limit_id=ALL_ENDPOINTS_LIMIT, limit=100, time_interval=1),
    RateLimit(
        limit_id=ORDER_PATH_URL, limit=50, time_interval=1, linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]
    ),
    RateLimit(
        limit_id=SERVER_LIMIT_INFO,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=ORDER_BATCH_PATH_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=ORDER_OPEN_PATH_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=ORDER_STATUS_PATH_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=BALANCE_PATH_URL,
        limit=100,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=BALANCE_HISTORY_PATH_URL,
        limit=8,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=HIST_PATH_URL, limit=60, time_interval=60, linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]
    ),
    RateLimit(
        limit_id=TICKER_PATH_URL, limit=100, time_interval=1, linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]
    ),
    RateLimit(
        limit_id=PRODUCTS_PATH_URL,
        limit=100,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=FEE_PATH_URL, limit=100, time_interval=1, linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]
    ),
    RateLimit(
        limit_id=TRADES_PATH_URL, limit=100, time_interval=1, linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]
    ),
    RateLimit(
        limit_id=DEPTH_PATH_URL, limit=100, time_interval=1, linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]
    ),
    RateLimit(
        limit_id=INFO_PATH_URL, limit=100, time_interval=1, linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]
    ),
    RateLimit(
        limit_id=SUB_ENDPOINT_NAME,
        limit=100,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=PONG_ENDPOINT_NAME,
        limit=100,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
]
