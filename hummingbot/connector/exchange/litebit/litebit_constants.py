# A single source of truth for constant variables related to the exchange
import sys

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.web_assistant.connections.data_types import RESTMethod

DEFAULT_DOMAIN = ""

HBOT_ORDER_ID_PREFIX = "hb-"
MAX_ORDER_ID_LEN = 32

EXCHANGE_NAME = "litebit"
REST_URL = "https://api.exchange.litebit.eu/"
WSS_URL = "wss://ws.exchange.litebit.eu/v1"

PUBLIC_API_VERSION = "v1"
PRIVATE_API_VERSION = "v1"

GET_MARKETS_PATH = '/markets'
GET_TICKERS_PATH = '/tickers'
GET_BOOK_PATH = '/book'
GET_TIME_PATH = '/time'
GET_ORDER_PATH = '/order'
CREATE_ORDER_PATH = '/order'
CANCEL_ORDERS_PATH = '/orders'
GET_BALANCES_PATH = '/balances'
GET_FILLS_PATH = '/fills'

API_REASONS = {}

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS = "ORDERS"
WS_CONNECTION = "WS_CONNECTION"
WS_REQUEST_COUNT = "WS_REQUEST_COUNT"

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1

NO_LIMIT = sys.maxsize

RATE_LIMITS = [
    # Pools
    RateLimit(limit_id=REQUEST_WEIGHT, limit=1000, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=WS_CONNECTION, limit=20, time_interval=ONE_MINUTE),
    RateLimit(limit_id=WS_REQUEST_COUNT, limit=50, time_interval=ONE_SECOND),

    # Weighted limits
    RateLimit(limit_id=GET_MARKETS_PATH, limit=NO_LIMIT, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=GET_TICKERS_PATH, limit=NO_LIMIT, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=GET_BOOK_PATH, limit=NO_LIMIT, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 5)]),
    RateLimit(limit_id=GET_TIME_PATH, limit=NO_LIMIT, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=f"{RESTMethod.GET}{GET_ORDER_PATH}", limit=NO_LIMIT, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=GET_FILLS_PATH, limit=NO_LIMIT, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 5)]),
    RateLimit(limit_id=GET_BALANCES_PATH, limit=NO_LIMIT, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 5)]),

    RateLimit(limit_id=f"{RESTMethod.POST}{CREATE_ORDER_PATH}", limit=NO_LIMIT, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(ORDERS, 1)]),
    RateLimit(limit_id=CANCEL_ORDERS_PATH, limit=NO_LIMIT, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(ORDERS, 1)]),
]
