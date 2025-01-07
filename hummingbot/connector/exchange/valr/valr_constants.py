from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = ''

HBOT_ORDER_ID_PREFIX = "HB-VR-"
MAX_ORDER_ID_LEN = 32

# Base URL
REST_URL = "https://api.valr.com"

# WEBSOCKET ENDPOINTS
WSS_URL = "wss://api.valr.com{}"
WSS_ACCOUNT_PATH_URL = "/ws/account"
WSS_TRADE_PATH_URL = "/ws/trade"
WSS_PING_INTERVAL = 20.0
WSS_USER_STREAM_LAST_RECEIVED_PONT_AT = 0


# REST API ENDPOINTS
GET_MARKET_SUMMARY_PATH_URL = "/v1/public/{}/marketsummary"
CREATE_LIMIT_ORDER_PATH_URL = "/v1/orders/limit"
CREATE_MARKET_ORDER_PATH = "/v1/orders/market"
CANCEL_ORDER_PATH_URL = "/v1/orders/order"
GET_BALANCES_PATH_URL = "/v1/account/balances"
GET_ORDER_DETAIL_PATH_URL = "/v1/orders/{}/orderid/{}"
GET_OPEN_ORDERS_PATH_URL = "/v1/orders/open"
GET_STATUS_PATH_URL = "/v1/public/status"
TRANSACTION_HISTORY = "/v1/account/transactionhistory?skip=0&limit=20&transactionTypes=LIMIT_BUY,MARKET_BUY,LIMIT_SELL,MARKET_SELL&currency={}"
TICKER_BOOK_PATH_URL = "/v1/public/marketsummary"
EXCHANGE_INFO_PATH_URL = "/v1/public/pairs"
PING_PATH_URL = "/v1/public/status"
SNAPSHOT_PATH_URL = "/v1/public/{}/orderbook"
SERVER_TIME_PATH_URL = "/v1/public/time"

# WSS SUBSCRIPTION TYPES
SNAPSHOT_CHANNEL_ID = "AGGREGATED_ORDERBOOK_UPDATE"
TRADE_CHANNEL_ID = "NEW_ACCOUNT_HISTORY_RECORD"
BALANCE_CHANNEL_ID = "BALANCE_UPDATE"
ORDER_CHANNEL_ID = "ORDER_STATUS_UPDATE"

# Valr params
SIDE_BUY = 'buy'
SIDE_SELL = 'sell'

ORDER_NOT_EXIST_ERROR_CODE = 404
ORDER_NOT_EXIST_MESSAGE = "Order does not exist"
UNKNOWN_ORDER_ERROR_CODE = 404
UNKNOWN_ORDER_MESSAGE = "Unknown order sent"

TIME_IN_FORCE_GTC = 'GTC'  # Good till cancelled
TIME_IN_FORCE_IOC = 'IOC'  # Immediate or cancel
TIME_IN_FORCE_FOK = 'FOK'  # Fill or kill

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
    "Placed": OrderState.OPEN,
    "Filled": OrderState.FILLED,
    "Partially Filled": OrderState.PARTIALLY_FILLED,
    "Cancelled": OrderState.CANCELED,
    "Failed": OrderState.CANCELED,
}

# Websocket event types
DIFF_EVENT_TYPE = "AGGREGATED_ORDERBOOK_UPDATE"
TRADE_EVENT_TYPE = "NEW_ACCOUNT_TRADE"

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
    RateLimit(limit_id=CREATE_LIMIT_ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=CREATE_MARKET_ORDER_PATH, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
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
    RateLimit(limit_id=TRANSACTION_HISTORY, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=TICKER_BOOK_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),                             
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=PING_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)])                             
]
