from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

# default chain: arbitrum goerli
DEFAULT_CHAIN_ID = 421613
DEFAULT_DOMAIN = "secret-thicket-93345.herokuapp.com"

# Base URL
REST_URL = "https://{}/api/"
WSS_URL = "ws://{}/"
WS_PING_TIMEOUT = 20 * 0.8
PUBLIC_API_VERSION = "v1"
PRIVATE_API_VERSION = "v1"

# API Websocket heartbeat
WS_HEARTBEAT_TIME_INTERVAL = 30

# Zigzag params
SIDE_BUY = 'b'
SIDE_SELL = 's'

TIME_IN_FORCE_GTC = 'GTC'  # Good till cancelled
TIME_IN_FORCE_IOC = 'IOC'  # Immediate or cancel
TIME_IN_FORCE_FOK = 'FOK'  # Fill or kill

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
WS_SUBSCRIBE = "WS_SUBSCRIBE"
ORDERS = "ORDERS"
ORDERS_24HR = "ORDERS_24HR"

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

# Max requests
MAX_REQUEST = 5000

# Order States
ORDER_STATE = {
    "PENDING": OrderState.PENDING_CREATE,
    "NEW": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "PENDING_CANCEL": OrderState.OPEN,
    "CANCELED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.FAILED,
}

# Websocket event types
DIFF_EVENT_TYPE = "depthUpdate"
TRADE_EVENT_TYPE = "trade"

MAX_ORDER_ID_LEN = 36

RATE_LIMITS = [
    # Pools
    RateLimit(limit_id=REQUEST_WEIGHT, limit=1200, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=ORDERS_24HR, limit=100000, time_interval=ONE_DAY),
    RateLimit(limit_id=WS_SUBSCRIBE, limit=1000, time_interval=ONE_MINUTE),
]
