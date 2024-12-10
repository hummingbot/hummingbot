from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "bitmart_perpetual"
BROKER_ID = "x-nbQe1H39"
MAX_ORDER_ID_LEN = 32

DOMAIN = EXCHANGE_NAME

PERPETUAL_BASE_URL = "https://api-cloud-v2.bitmart.com"
PERPETUAL_WS_URL = "wss://openapi-ws-v2.bitmart.com"

SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 20
PUBLIC_WS_ENDPOINT = "/api?protocol=1.1"
PRIVATE_WS_ENDPOINT = "/user?protocol=1.1"

TIME_IN_FORCE_GTC = "GTC"  # Good till cancelled
TIME_IN_FORCE_MAKER_ONLY = "GTX"  # Good Till Crossing
TIME_IN_FORCE_IOC = "IOC"  # Immediate or cancel
TIME_IN_FORCE_FOK = "FOK"  # Fill or kill

# Public API v1 Endpoints
SNAPSHOT_REST_URL = "/contract/public/depth"
TICKER_PRICE_URL = "v1/ticker/bookTicker"
TICKER_PRICE_CHANGE_URL = "v1/ticker/24hr"
EXCHANGE_INFO_URL = "/contract/public/details"
RECENT_TRADES_URL = "v1/trades"
PING_URL = "v1/ping"
FUNDING_INFO_URL = "/contract/public/funding-rate"
SERVER_TIME_PATH_URL = "/system/time"

# Private API v1 Endpoints
SUBMIT_ORDER_URL = "/contract/private/submit-order"
ORDER_DETAILS = "/contract/private/order"
ALL_OPEN_ORDERS = "/contract/private/get-open-orders"
CANCEL_ORDER_URL = "/contract/private/cancel-order"
CANCEL_ALL_OPEN_ORDERS_URL = "v1/allOpenOrders"
ACCOUNT_TRADE_LIST_URL = "/contract/private/trades"
SET_LEVERAGE_URL = "/contract/private/submit-leverage"
GET_INCOME_HISTORY_URL = "v1/income"

# Private API v2 Endpoints
ACCOUNT_INFO_URL = "/contract/private/order"
ASSETS_DETAIL = "/contract/private/assets-detail"
POSITION_INFORMATION_URL = "/contract/private/position"

# Public WS channels
DIFF_STREAM_CHANNEL = "futures/depth50"
TRADE_STREAM_CHANNEL = "futures/trade"
FUNDING_INFO_CHANNEL = "futures/fundingRate"
TICKERS_CHANNEL = "futures/ticker"
SNAPSHOT_CHANNEL = "futures/depthAll50"

# Private WS channels
WS_POSITIONS_CHANNEL = "futures/position"
WS_ORDERS_CHANNEL = "futures/order"
WS_ACCOUNT_CHANNEL = "futures/asset:USDT"

# Funding Settlement Time Span
FUNDING_SETTLEMENT_DURATION = (0, 30)  # seconds before snapshot, seconds after snapshot

# Order Statuses
ORDER_STATE = {
    "NEW": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "CANCELED": OrderState.CANCELED,
    "EXPIRED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
}

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS_1MIN = "ORDERS_1MIN"
ORDERS_1SEC = "ORDERS_1SEC"

HEARTBEAT_TIME_INTERVAL = 30.0

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
    RateLimit(limit_id=TICKER_PRICE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=2)]),
    RateLimit(limit_id=TICKER_PRICE_CHANGE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=EXCHANGE_INFO_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=40)]),
    RateLimit(limit_id=RECENT_TRADES_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=PING_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=SUBMIT_ORDER_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1),
                             LinkedLimitWeightPair(ORDERS_1MIN, weight=1),
                             LinkedLimitWeightPair(ORDERS_1SEC, weight=1)]),
    RateLimit(limit_id=CANCEL_ALL_OPEN_ORDERS_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=ACCOUNT_TRADE_LIST_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=SET_LEVERAGE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=GET_INCOME_HISTORY_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=30)]),
    RateLimit(limit_id=ACCOUNT_INFO_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=ASSETS_DETAIL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=POSITION_INFORMATION_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=5,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=FUNDING_INFO_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=5,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    # RateLimit(limit_id=MARK_PRICE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=1,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
]

ORDER_NOT_EXIST_ERROR_CODE = 40035
ORDER_NOT_EXIST_MESSAGE = "The order is not exist"
UNKNOWN_ORDER_ERROR_CODE = 40037
UNKNOWN_ORDER_MESSAGE = "The order id is not exist"
