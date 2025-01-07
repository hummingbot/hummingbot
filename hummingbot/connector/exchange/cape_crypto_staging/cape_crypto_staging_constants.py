from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = ''

HBOT_ORDER_ID_PREFIX = "HB-CC-"
MAX_ORDER_ID_LEN = 32

# Base URL
REST_URL = "https://staging.capecrypto.com/api/v2/peatio"

# WEBSOCKET ENDPOINTS
WSS_PRIVATE_URL = "wss://staging.capecrypto.com/api/v2/ranger/private?stream=order&stream=trade&stream=balance"
WSS_PUBLIC_URL = "wss://staging.capecrypto.com/api/v2/ranger/public{}"
WSS_PING_INTERVAL = 20.0

# REST API ENDPOINTS
GET_MARKET_SUMMARY_PATH_URL = "/public/markets"
GET_MARKET_TICKER_PATH_URL = "/public/markets/{}/tickers"
CREATE_ORDER_PATH_URL = "/market/orders"
CANCEL_ORDER_PATH_URL = "/market/orders/{}/cancel"
CANCEL_ALL_ORDERS_PATH_URL = "/market/orders/cancel"
GET_BALANCES_PATH_URL = "/account/balances"
GET_ORDER_DETAIL_PATH_URL = "/market/orders/{}"
GET_OPEN_ORDERS_PATH_URL = "/market/orders/"
GET_STATUS_PATH_URL = "/public/health/alive"
TICKER_BOOK_PATH_URL = "/public/markets/tickers"
SNAPSHOT_PATH_URL = "/public/markets/{}/order-book"
SERVER_TIME_PATH_URL = "/public/timestamp"

# WSS SUBSCRIPTION TYPES
SNAPSHOT_CHANNEL_ID = "ob-snap"
DIFF_EVENT_TYPE = "ob-inc"
TRADE_CHANNEL_ID = "trade"
ORDER_CHANNEL_ID = "order"
BALANCE_CHANNEL_ID = "balance"
TRADE_EVENT_TYPE = "trade"

# CapeCryptoStaging params
SIDE_BUY = 'buy'
SIDE_SELL = 'sell'

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS = "ORDERS"
ORDERS_24HR = "ORDERS_24HR"
RAW_REQUESTS = "RAW_REQUESTS"

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 5000

# Order States
ORDER_STATE = {
    "pending": OrderState.PENDING_CREATE,
    "wait": OrderState.OPEN,
    "done": OrderState.FILLED,
    "Partially Filled": OrderState.PARTIALLY_FILLED,
    "cancel": OrderState.CANCELED,
    "failed": OrderState.CANCELED,
}

RATE_LIMITS = [
    # Pools
    RateLimit(limit_id=REQUEST_WEIGHT, limit=1200, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS, limit=50, time_interval=10 * ONE_SECOND),
    RateLimit(limit_id=ORDERS_24HR, limit=160000, time_interval=ONE_DAY),
    RateLimit(limit_id=RAW_REQUESTS, limit=6100, time_interval= 5 * ONE_MINUTE),
    
    # Weighted Limits
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=GET_MARKET_SUMMARY_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=CREATE_ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=CANCEL_ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=GET_BALANCES_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=GET_ORDER_DETAIL_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=GET_OPEN_ORDERS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT,1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=GET_STATUS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=CANCEL_ALL_ORDERS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=TICKER_BOOK_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),                             
    RateLimit(limit_id=GET_MARKET_TICKER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)])                             
]
