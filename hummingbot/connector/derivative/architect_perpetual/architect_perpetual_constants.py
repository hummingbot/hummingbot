from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "architect_perpetual"
BROKER_ID = "hummingbot"
MAX_ORDER_ID_LEN = 36

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "architect_perpetual_testnet"

REST_BASE_URL = "https://api.architect.co"
TESTNET_REST_BASE_URL = "https://api.sandbox.architect.co"

WS_BASE_URL = "wss://api.architect.co/ws"
TESTNET_WS_BASE_URL = "wss://api.sandbox.architect.co/ws"

TIME_IN_FORCE_GTC = "GTC"
TIME_IN_FORCE_GTD = "GTD"
TIME_IN_FORCE_IOC = "IOC"
TIME_IN_FORCE_FOK = "FOK"
TIME_IN_FORCE_DAY = "DAY"

MARKETS_ENDPOINT = "/v1/markets"
ORDERBOOK_ENDPOINT = "/v1/orderbook"
TRADES_ENDPOINT = "/v1/trades"
ACCOUNT_ENDPOINT = "/v1/account"
ORDERS_ENDPOINT = "/v1/orders"
POSITIONS_ENDPOINT = "/v1/positions"
BALANCES_ENDPOINT = "/v1/balances"

ORDER_STATE = {
    "PENDING": OrderState.PENDING_CREATE,
    "OPEN": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "CANCELED": OrderState.CANCELED,
    "CANCELLED": OrderState.CANCELED,
    "EXPIRED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "FAILED": OrderState.FAILED,
}

REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS_1MIN = "ORDERS_1MIN"

ONE_MINUTE = 60
ONE_SECOND = 1
ONE_HOUR = 3600

MAX_REQUESTS_PER_MINUTE = 1200
MAX_ORDERS_PER_MINUTE = 300

RATE_LIMITS = [
    RateLimit(limit_id=REQUEST_WEIGHT, limit=MAX_REQUESTS_PER_MINUTE, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS_1MIN, limit=MAX_ORDERS_PER_MINUTE, time_interval=ONE_MINUTE),
    RateLimit(limit_id=MARKETS_ENDPOINT, limit=MAX_REQUESTS_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=ORDERBOOK_ENDPOINT, limit=MAX_REQUESTS_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=TRADES_ENDPOINT, limit=MAX_REQUESTS_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=ACCOUNT_ENDPOINT, limit=MAX_REQUESTS_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=ORDERS_ENDPOINT, limit=MAX_REQUESTS_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1), LinkedLimitWeightPair(ORDERS_1MIN, weight=1)]),
    RateLimit(limit_id=POSITIONS_ENDPOINT, limit=MAX_REQUESTS_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=BALANCES_ENDPOINT, limit=MAX_REQUESTS_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
]

DIFF_STREAM_ID = 1
TRADE_STREAM_ID = 2
USER_STREAM_ID = 3

HEARTBEAT_TIME_INTERVAL = 30.0
FUNDING_SETTLEMENT_DURATION = (0, 30)

ORDER_NOT_FOUND_ERROR = "ORDER_NOT_FOUND"
INSUFFICIENT_BALANCE_ERROR = "INSUFFICIENT_BALANCE"
INVALID_ORDER_ERROR = "INVALID_ORDER"

DEFAULT_QUOTE_ASSET = "USD"
