from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "hashkey_perpetual"
DEFAULT_DOMAIN = "hashkey_perpetual"
HBOT_BROKER_ID = "10000800001"
BROKER_ID = "HASHKEY-"
MAX_ORDER_ID_LEN = 32

TESTNET_DOMAIN = "hashkey_perpetual_testnet"

PERPETUAL_BASE_URL = "https://api-glb.hashkey.com"
TESTNET_BASE_URL = "https://api-glb.sim.hashkeydev.com"

WSS_PUBLIC_URL = {"hashkey_perpetual": "wss://stream-glb.hashkey.com/quote/ws/v1",
                  "hashkey_perpetual_testnet": "wss://stream.sim.bmuxdc.com/quote/ws/v1"}

WSS_PRIVATE_URL = {"hashkey_perpetual": "wss://stream-glb.hashkey.com/api/v1/ws/{listenKey}",
                   "hashkey_perpetual_testnet": "wss://stream.sim.bmuxdc.com/api/v1/ws/{listenKey}"}

# Websocket event types
TRADE_EVENT_TYPE = "trade"
SNAPSHOT_EVENT_TYPE = "depth"

TIME_IN_FORCE_GTC = "GTC"  # Good till cancelled
TIME_IN_FORCE_MAKER = "LIMIT_MAKER"  # Maker
TIME_IN_FORCE_IOC = "IOC"  # Immediate or cancel
TIME_IN_FORCE_FOK = "FOK"  # Fill or kill

# Public API Endpoints
SNAPSHOT_PATH_URL = "/quote/v1/depth"
TICKER_PRICE_URL = "/quote/v1/ticker/price"
TICKER_PRICE_CHANGE_URL = "/quote/v1/ticker/24hr"
EXCHANGE_INFO_URL = "/api/v1/exchangeInfo"
RECENT_TRADES_URL = "/quote/v1/trades"
PING_URL = "/api/v1/ping"
SERVER_TIME_PATH_URL = "/api/v1/time"

# Public funding info
FUNDING_INFO_URL = "/api/v1/futures/fundingRate"
MARK_PRICE_URL = "/quote/v1/markPrice"
INDEX_PRICE_URL = "/quote/v1/index"

# Private API Endpoints
ACCOUNT_INFO_URL = "/api/v1/futures/balance"
POSITION_INFORMATION_URL = "/api/v1/futures/positions"
ORDER_URL = "/api/v1/futures/order"
CANCEL_ALL_OPEN_ORDERS_URL = "/api/v1/futures/batchOrders"
ACCOUNT_TRADE_LIST_URL = "/api/v1/futures/userTrades"
SET_LEVERAGE_URL = "/api/v1/futures/leverage"
USER_STREAM_PATH_URL = "/api/v1/userDataStream"

# Funding Settlement Time Span
FUNDING_SETTLEMENT_DURATION = (0, 30)  # seconds before snapshot, seconds after snapshot

# Order States
ORDER_STATE = {
    "PENDING": OrderState.PENDING_CREATE,
    "NEW": OrderState.OPEN,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "FILLED": OrderState.FILLED,
    "PENDING_CANCEL": OrderState.PENDING_CANCEL,
    "CANCELED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "PARTIALLY_CANCELED": OrderState.CANCELED,
}

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS_1MIN = "ORDERS_1MIN"
ORDERS_1SEC = "ORDERS_1SEC"

WS_HEARTBEAT_TIME_INTERVAL = 30.0

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
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=20)]),
    RateLimit(limit_id=TICKER_PRICE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=2)]),
    RateLimit(limit_id=TICKER_PRICE_CHANGE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=EXCHANGE_INFO_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=40)]),
    RateLimit(limit_id=RECENT_TRADES_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=USER_STREAM_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=PING_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=ORDER_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1),
                             LinkedLimitWeightPair(ORDERS_1MIN, weight=1),
                             LinkedLimitWeightPair(ORDERS_1SEC, weight=1)]),
    RateLimit(limit_id=CANCEL_ALL_OPEN_ORDERS_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=ACCOUNT_TRADE_LIST_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=SET_LEVERAGE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=ACCOUNT_INFO_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=POSITION_INFORMATION_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=5,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=MARK_PRICE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=1,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=INDEX_PRICE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=1,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=FUNDING_INFO_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=1,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
]

ORDER_NOT_EXIST_ERROR_CODE = -1143
ORDER_NOT_EXIST_MESSAGE = "Order not found"
