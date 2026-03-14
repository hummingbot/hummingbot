from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "grvt_perpetual"
BROKER_ID = "hummingbot"
MAX_ORDER_ID_LEN = 36

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "grvt_perpetual_testnet"

# GRVT API Endpoints
# Mainnet: https://api.grvt.io
# Testnet: https://api-testnet.grvt.io
PERPETUAL_BASE_URL = "https://api.grvt.io/"
TESTNET_BASE_URL = "https://api-testnet.grvt.io/"

PERPETUAL_WS_URL = "wss://ws.grvt.io/"
TESTNET_WS_URL = "wss://ws-testnet.grvt.io/"

PUBLIC_WS_ENDPOINT = "ws"
PRIVATE_WS_ENDPOINT = "ws/private"

TIME_IN_FORCE_GTC = "GTC"  # Good till cancelled
TIME_IN_FORCE_GTX = "GTX"  # Good Till Crossing
TIME_IN_FORCE_IOC = "IOC"  # Immediate or cancel
TIME_IN_FORCE_FOK = "FOK"  # Fill or kill

# Public API Endpoints
SNAPSHOT_REST_URL = "derivatives/v1/market/depth"
TICKER_PRICE_URL = "derivatives/v1/market/ticker"
TICKER_PRICE_CHANGE_URL = "derivatives/v1/market/ticker/24hr"
EXCHANGE_INFO_URL = "derivatives/v1/market/exchangeInfo"
RECENT_TRADES_URL = "derivatives/v1/market/trades"
PING_URL = "derivatives/v1/market/ping"
SERVER_TIME_PATH_URL = "derivatives/v1/market/time"
MARK_PRICE_URL = "derivatives/v1/market/mark_price"

# Private API Endpoints
ORDER_URL = "derivatives/v1/order"
CANCEL_ALL_OPEN_ORDERS_URL = "derivatives/v1/order/allOpenOrders"
ACCOUNT_TRADE_LIST_URL = "derivatives/v1/userTrades"
SET_LEVERAGE_URL = "derivatives/v1/account/leverage"
GET_INCOME_HISTORY_URL = "derivatives/v1/account/income"
CHANGE_POSITION_MODE_URL = "derivatives/v1/account/positionMode"

# Private API v2 Endpoints
ACCOUNT_INFO_URL = "derivatives/v2/account"
POSITION_INFORMATION_URL = "derivatives/v2/positionRisk"

# User Stream
GRVT_USER_STREAM_ENDPOINT = "derivatives/v1/user/auth"
GRVT_WS_AUTH_ENDPOINT = "auth"

# Funding Settlement Time Span
FUNDING_SETTLEMENT_DURATION = (0, 30)  # seconds before snapshot, seconds after snapshot

# Order Statuses
ORDER_STATE = {
    "NEW": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "CANCELED": OrderState.CANCELED,
    "CANCELLED": OrderState.CANCELED,
    "EXPIRED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
}

# Stream IDs
DIFF_STREAM_ID = 1
TRADE_STREAM_ID = 2
FUNDING_INFO_STREAM_ID = 3
HEARTBEAT_TIME_INTERVAL = 30.0

# Rate Limit time intervals
ONE_HOUR = 3600
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 1200

RATE_LIMITS = [
    # Pool Limits
    RateLimit(limit_id="REQUEST_WEIGHT", limit=MAX_REQUEST, time_interval=ONE_MINUTE),
    RateLimit(limit_id="ORDERS_1MIN", limit=600, time_interval=ONE_MINUTE),
    RateLimit(limit_id="ORDERS_1SEC", limit=150, time_interval=10),
    # Weight Limits for individual endpoints
    RateLimit(limit_id=SNAPSHOT_REST_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair("REQUEST_WEIGHT", weight=20)]),
    RateLimit(limit_id=TICKER_PRICE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair("REQUEST_WEIGHT", weight=2)]),
    RateLimit(limit_id=TICKER_PRICE_CHANGE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair("REQUEST_WEIGHT", weight=1)]),
    RateLimit(limit_id=EXCHANGE_INFO_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair("REQUEST_WEIGHT", weight=40)]),
    RateLimit(limit_id=RECENT_TRADES_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair("REQUEST_WEIGHT", weight=1)]),
    RateLimit(limit_id=GRVT_USER_STREAM_ENDPOINT, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair("REQUEST_WEIGHT", weight=1)]),
    RateLimit(limit_id=PING_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair("REQUEST_WEIGHT", weight=1)]),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair("REQUEST_WEIGHT", weight=1)]),
    RateLimit(limit_id=ORDER_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair("REQUEST_WEIGHT", weight=1),
                             LinkedLimitWeightPair("ORDERS_1MIN", weight=1),
                             LinkedLimitWeightPair("ORDERS_1SEC", weight=1)]),
    RateLimit(limit_id=CANCEL_ALL_OPEN_ORDERS_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair("REQUEST_WEIGHT", weight=1)]),
    RateLimit(limit_id=ACCOUNT_TRADE_LIST_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair("REQUEST_WEIGHT", weight=5)]),
    RateLimit(limit_id=SET_LEVERAGE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair("REQUEST_WEIGHT", weight=1)]),
    RateLimit(limit_id=GET_INCOME_HISTORY_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair("REQUEST_WEIGHT", weight=30)]),
    RateLimit(limit_id=CHANGE_POSITION_MODE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair("REQUEST_WEIGHT", weight=1)]),
    RateLimit(limit_id=ACCOUNT_INFO_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair("REQUEST_WEIGHT", weight=5)]),
    RateLimit(limit_id=POSITION_INFORMATION_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=5,
              linked_limits=[LinkedLimitWeightPair("REQUEST_WEIGHT", weight=5)]),
    RateLimit(limit_id=MARK_PRICE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=1,
              linked_limits=[LinkedLimitWeightPair("REQUEST_WEIGHT", weight=1)]),
]

# Error codes
ORDER_NOT_EXIST_ERROR_CODE = -1
ORDER_NOT_EXIST_MESSAGE = "Order does not exist"
UNKNOWN_ORDER_ERROR_CODE = -1
UNKNOWN_ORDER_MESSAGE = "Unknown order"
