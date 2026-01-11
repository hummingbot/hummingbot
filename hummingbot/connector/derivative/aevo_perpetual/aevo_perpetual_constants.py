from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "aevo_perpetual"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = 36

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "aevo_perpetual_testnet"

PERPETUAL_BASE_URL = "https://api.aevo.xyz"
TESTNET_BASE_URL = "https://api-testnet.aevo.xyz"

PERPETUAL_WS_URL = "wss://ws.aevo.xyz"
TESTNET_WS_URL = "wss://ws-testnet.aevo.xyz"

FUNDING_RATE_UPDATE_INTERVAL_SECONDS = 60

TIME_IN_FORCE_GTC = "gtc"
TIME_IN_FORCE_IOC = "ioc"
TIME_IN_FORCE_FOK = "fok"

SNAPSHOT_REST_URL = "/orderbook"
TICKER_PRICE_URL = "/ticker"
EXCHANGE_INFO_URL = "/markets"
MARKETS_URL = "/markets"
PING_URL = "/time"
SERVER_TIME_PATH_URL = "/time"
MARK_PRICE_URL = "/mark-price"
INDEX_URL = "/index"
FUNDING_RATE_URL = "/funding"

ORDER_URL = "/orders"
CANCEL_ORDER_URL = "/orders"
ACCOUNT_INFO_URL = "/account"
POSITION_INFORMATION_URL = "/positions"
SET_LEVERAGE_URL = "/account/leverage"
ACCOUNT_TRADE_LIST_URL = "/trade-history"
GET_INCOME_HISTORY_URL = "/funding-history"

ORDER_STATE = {
    "open": OrderState.OPEN,
    "pending": OrderState.PENDING_CREATE,
    "filled": OrderState.FILLED,
    "partial": OrderState.PARTIALLY_FILLED,
    "cancelled": OrderState.CANCELED,
    "expired": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
}

DIFF_STREAM_ID = 1
TRADE_STREAM_ID = 2
FUNDING_INFO_STREAM_ID = 3
HEARTBEAT_TIME_INTERVAL = 30.0

ONE_HOUR = 3600
ONE_MINUTE = 60
ONE_SECOND = 1

MAX_REQUEST = 100
ALL_ENDPOINTS_LIMIT = "All"

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=MAX_REQUEST, time_interval=ONE_SECOND),
    RateLimit(limit_id=SNAPSHOT_REST_URL, limit=MAX_REQUEST, time_interval=ONE_SECOND,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=TICKER_PRICE_URL, limit=MAX_REQUEST, time_interval=ONE_SECOND,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=EXCHANGE_INFO_URL, limit=MAX_REQUEST, time_interval=ONE_SECOND,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=PING_URL, limit=MAX_REQUEST, time_interval=ONE_SECOND,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_SECOND,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ORDER_URL, limit=MAX_REQUEST, time_interval=ONE_SECOND,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=CANCEL_ORDER_URL, limit=MAX_REQUEST, time_interval=ONE_SECOND,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ACCOUNT_INFO_URL, limit=MAX_REQUEST, time_interval=ONE_SECOND,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=POSITION_INFORMATION_URL, limit=MAX_REQUEST, time_interval=ONE_SECOND,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=SET_LEVERAGE_URL, limit=MAX_REQUEST, time_interval=ONE_SECOND,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ACCOUNT_TRADE_LIST_URL, limit=MAX_REQUEST, time_interval=ONE_SECOND,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=GET_INCOME_HISTORY_URL, limit=MAX_REQUEST, time_interval=ONE_SECOND,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=MARK_PRICE_URL, limit=MAX_REQUEST, time_interval=ONE_SECOND,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=FUNDING_RATE_URL, limit=MAX_REQUEST, time_interval=ONE_SECOND,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
]

ORDER_NOT_EXIST_ERROR_CODE = "ORDER_NOT_FOUND"
ORDER_NOT_EXIST_MESSAGE = "Order not found"
UNKNOWN_ORDER_ERROR_CODE = "UNKNOWN_ORDER"
UNKNOWN_ORDER_MESSAGE = "Unknown order"
