from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "coinflex"

HBOT_ORDER_ID_PREFIX = "48"
USER_AGENT = "HBOT"

# Base URL
REST_URL = "{}api.coinflex.com"
WSS_URL = "wss://{}api.coinflex.com/{}/websocket"

PUBLIC_API_VERSION = "v2"
PRIVATE_API_VERSION = "v2"

# Public API endpoints or CoinflexClient function
TICKER_PRICE_CHANGE_PATH_URL = "ticker"
EXCHANGE_INFO_PATH_URL = "all/markets"
PING_PATH_URL = "ping"
SNAPSHOT_PATH_URL = "depth/{}/{}"

# Private API endpoints or CoinflexClient function
ACCOUNTS_PATH_URL = "balances"
ORDER_PATH_URL = "orders"
ORDER_CREATE_PATH_URL = "orders/place"
ORDER_CANCEL_PATH_URL = "orders/cancel"

WS_CHANNELS = {
    "USER_STREAM": [
        "balance:all",
        "position:all",
        "order:all",
    ]
}

WS_HEARTBEAT_TIME_INTERVAL = 30
MESSAGE_TIMEOUT = 30.0
PING_TIMEOUT = 10.0
API_CALL_TIMEOUT = 10.0
API_MAX_RETRIES = 3

# CoinFLEX params

SIDE_BUY = 'BUY'
SIDE_SELL = 'SELL'

TIME_IN_FORCE_GTC = 'GTC'         # Good till cancelled
TIME_IN_FORCE_IOC = 'IOC'         # Immediate or cancel
TIME_IN_FORCE_FOK = 'FOK'         # Fill or kill
TIME_IN_FORCE_MAK = 'MAKER_ONLY'  # Maker

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS = "ORDERS"
ORDERS_24HR = "ORDERS_24HR"

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 5000

# Order States
ORDER_CANCELED_STATES = [
    "OrderClosed",
    "cancelOrder",
    "CANCELED",
    "CANCELED_BY_USER",
    "CANCELED_BY_MAKER_ONLY",
    "CANCELED_BY_FOK",
    "CANCELED_ALL_BY_IOC",
    "CANCELED_PARTIAL_BY_IOC",
    "CANCELED_BY_AMEND",
]

ORDER_STATE = {
    "PENDING": OrderState.PENDING_CREATE,
    "placeOrder": OrderState.OPEN,
    "OrderOpened": OrderState.OPEN,
    "OPEN": OrderState.OPEN,
    "OrderMatched": OrderState.FILLED,
    "FILLED": OrderState.FILLED,
    "PARTIAL_FILL": OrderState.PARTIALLY_FILLED,
    "PENDING_CANCEL": OrderState.OPEN,
    "REJECT_CANCEL_ORDER_ID_NOT_FOUND": OrderState.FAILED,
    "EXPIRED": OrderState.FAILED,
}

for state in ORDER_CANCELED_STATES:
    ORDER_STATE[state] = OrderState.CANCELED

ORDER_NOT_FOUND_ERRORS = [
    "Open order not found with clientOrderId or orderId",
    "Order request was rejected with status REJECT_CANCEL_ORDER_ID_NOT_FOUND"
]

# Websocket event types
DIFF_EVENT_TYPE = "depth"
TRADE_EVENT_TYPE = "trade"

RATE_LIMITS = [
    # Pools
    RateLimit(limit_id=REQUEST_WEIGHT, limit=1200, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=ORDERS_24HR, limit=100000, time_interval=ONE_DAY),
    # Weighted Limits
    RateLimit(limit_id=TICKER_PRICE_CHANGE_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 40)]),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[(LinkedLimitWeightPair(REQUEST_WEIGHT, 10))]),
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 50)]),
    RateLimit(limit_id=PING_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10)]),
    RateLimit(limit_id=ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(ORDERS, 1),
                             LinkedLimitWeightPair(ORDERS_24HR, 1)]),
    RateLimit(limit_id=ORDER_CREATE_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(ORDERS, 1),
                             LinkedLimitWeightPair(ORDERS_24HR, 1)]),
    RateLimit(limit_id=ORDER_CANCEL_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(ORDERS, 1),
                             LinkedLimitWeightPair(ORDERS_24HR, 1)]),
]
