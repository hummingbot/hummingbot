from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "coinflex_perpetual"
HBOT_ORDER_ID_PREFIX = "48"
USER_AGENT = "HBOT"

DEFAULT_DOMAIN = EXCHANGE_NAME

REST_URL = "{}api.coinflex.com"
WSS_URL = "wss://{}api.coinflex.com/{}/websocket"

PUBLIC_API_VERSION = "v2"
PRIVATE_API_VERSION = "v2"


# Public API v1 Endpoints
SNAPSHOT_REST_URL = "depth/{}/{}"
TICKER_PRICE_CHANGE_URL = "ticker"
EXCHANGE_INFO_URL = "all/markets"
PING_URL = "ping"
MARK_PRICE_URL = "delivery/public/funding"

# Private API v1 Endpoints
ORDER_STATUS_URL = "orders"
ORDER_CREATE_URL = "orders/place"
ORDER_CANCEL_URL = "orders/cancel"
SET_LEVERAGE_URL = "/leverage"
GET_INCOME_HISTORY_URL = "funding-payments"
CHANGE_POSITION_MODE_URL = "/positionSide/dual"

POST_POSITION_MODE_LIMIT_ID = f"POST{CHANGE_POSITION_MODE_URL}"
GET_POSITION_MODE_LIMIT_ID = f"GET{CHANGE_POSITION_MODE_URL}"

# Private API v2 Endpoints
ACCOUNT_INFO_URL = "balances"
POSITION_INFORMATION_URL = "positions"

# Funding Settlement Time Span
FUNDING_SETTLEMENT_DURATION = (0, 30)  # seconds before snapshot, seconds after snapshot

# Websocket Channels
WS_CHANNELS = {
    "USER_STREAM": [
        "balance:all",
        "position:all",
        "order:all",
    ]
}

# Order States
ORDER_CANCELLED_STATES = [
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

for state in ORDER_CANCELLED_STATES:
    ORDER_STATE[state] = OrderState.CANCELED

ORDER_NOT_FOUND_ERRORS = [
    "Open order not found with clientOrderId or orderId",
    "Order request was rejected with status REJECT_CANCEL_ORDER_ID_NOT_FOUND"
]

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS_1MIN = "ORDERS_1MIN"
ORDERS_1SEC = "ORDERS_1SEC"

DIFF_STREAM_ID = "depth"
TRADE_STREAM_ID = "trade"
HEARTBEAT_TIME_INTERVAL = 30.0
API_CALL_TIMEOUT = 10.0
API_MAX_RETRIES = 3

SIDE_BUY = 'BUY'
SIDE_SELL = 'SELL'

TIME_IN_FORCE_GTC = 'GTC'         # Good till cancelled
TIME_IN_FORCE_IOC = 'IOC'         # Immediate or cancel
TIME_IN_FORCE_FOK = 'FOK'         # Fill or kill
TIME_IN_FORCE_MAK = 'MAKER_ONLY'  # Maker

# Rate Limit time intervals
ONE_HOUR = 3600
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 2400

RATE_LIMITS = [
    # Pool Limits
    RateLimit(limit_id=REQUEST_WEIGHT, limit=2400, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS_1MIN, limit=1200, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS_1SEC, limit=300, time_interval=10),
    # Weight Limits for individual endpoints
    RateLimit(limit_id=SNAPSHOT_REST_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=20)]),
    RateLimit(limit_id=TICKER_PRICE_CHANGE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=EXCHANGE_INFO_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=40)]),
    RateLimit(limit_id=PING_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=ORDER_STATUS_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1),
                             LinkedLimitWeightPair(ORDERS_1MIN, weight=1),
                             LinkedLimitWeightPair(ORDERS_1SEC, weight=1)]),
    RateLimit(limit_id=ORDER_CREATE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1),
                             LinkedLimitWeightPair(ORDERS_1MIN, weight=1),
                             LinkedLimitWeightPair(ORDERS_1SEC, weight=1)]),
    RateLimit(limit_id=ORDER_CANCEL_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1),
                             LinkedLimitWeightPair(ORDERS_1MIN, weight=1),
                             LinkedLimitWeightPair(ORDERS_1SEC, weight=1)]),
    RateLimit(limit_id=SET_LEVERAGE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=GET_INCOME_HISTORY_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=30)]),
    RateLimit(limit_id=POST_POSITION_MODE_LIMIT_ID, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=GET_POSITION_MODE_LIMIT_ID, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=30)]),
    RateLimit(limit_id=ACCOUNT_INFO_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=POSITION_INFORMATION_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=5,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=MARK_PRICE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=1,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
]
