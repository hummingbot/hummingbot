from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "exchange"

REST_URL = "https://api.backpack.{}/"
WSS_URL = "wss://ws.backpack.{}/"


WS_HEARTBEAT_TIME_INTERVAL = 60
MAX_ORDER_ID_LEN = 32  # Full uint32 bit space
HBOT_ORDER_ID_PREFIX = ""  # No prefix - use full ID space for uniqueness
BROKER_ID = 2200

ALL_ORDERS_CHANNEL = "account.orderUpdate"
SINGLE_ORDERS_CHANNEL = "account.orderUpdate.{}"  # format by symbol

SIDE_BUY = "Bid"
SIDE_SELL = "Ask"
TIME_IN_FORCE_GTC = "GTC"
ORDER_STATE = {
    "Cancelled": OrderState.CANCELED,
    "Expired": OrderState.CANCELED,
    "Filled": OrderState.FILLED,
    "New": OrderState.OPEN,
    "PartiallyFilled": OrderState.PARTIALLY_FILLED,
    "TriggerPending": OrderState.PENDING_CREATE,
    "TriggerFailed": OrderState.FAILED,
}

DIFF_EVENT_TYPE = "depth"
TRADE_EVENT_TYPE = "trade"

PING_PATH_URL = "api/v1/ping"
SERVER_TIME_PATH_URL = "api/v1/time"
EXCHANGE_INFO_PATH_URL = "api/v1/markets"
SNAPSHOT_PATH_URL = "api/v1/depth"
BALANCE_PATH_URL = "api/v1/capital"  # instruction balanceQuery
TICKER_BOOK_PATH_URL = "api/v1/tickers"
TICKER_PRICE_CHANGE_PATH_URL = "api/v1/ticker"
ORDER_PATH_URL = "api/v1/order"
MY_TRADES_PATH_URL = "wapi/v1/history/fills"

GLOBAL_RATE_LIMIT = "GLOBAL"

# Present in https://support.backpack.exchange/exchange/api-and-developer-docs/faqs, not in the docs
RATE_LIMITS = [
    # Global pool limit
    RateLimit(limit_id=GLOBAL_RATE_LIMIT, limit=2000, time_interval=60),
    # All endpoints linked to the global pool
    RateLimit(
        limit_id=SERVER_TIME_PATH_URL,
        limit=2000,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(GLOBAL_RATE_LIMIT)],
    ),
    RateLimit(
        limit_id=EXCHANGE_INFO_PATH_URL,
        limit=2000,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(GLOBAL_RATE_LIMIT)],
    ),
    RateLimit(
        limit_id=PING_PATH_URL,
        limit=2000,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(GLOBAL_RATE_LIMIT)],
    ),
    RateLimit(
        limit_id=SNAPSHOT_PATH_URL,
        limit=2000,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(GLOBAL_RATE_LIMIT)],
    ),
    RateLimit(
        limit_id=BALANCE_PATH_URL,
        limit=2000,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(GLOBAL_RATE_LIMIT)],
    ),
    RateLimit(
        limit_id=TICKER_BOOK_PATH_URL,
        limit=2000,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(GLOBAL_RATE_LIMIT)],
    ),
    RateLimit(
        limit_id=TICKER_PRICE_CHANGE_PATH_URL,
        limit=2000,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(GLOBAL_RATE_LIMIT)],
    ),
    RateLimit(
        limit_id=ORDER_PATH_URL,
        limit=2000,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(GLOBAL_RATE_LIMIT)],
    ),
    RateLimit(
        limit_id=MY_TRADES_PATH_URL,
        limit=2000,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(GLOBAL_RATE_LIMIT)],
    ),
]

ORDER_NOT_EXIST_ERROR_CODE = "RESOURCE_NOT_FOUND"
ORDER_NOT_EXIST_MESSAGE = "Not Found"
UNKNOWN_ORDER_ERROR_CODE = "RESOURCE_NOT_FOUND"
UNKNOWN_ORDER_MESSAGE = "Not Found"
