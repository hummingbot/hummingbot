from hummingbot.core.api_throttler.data_types import RateLimit

EXCHANGE_NAME = "bitmart_perpetual"
BROKER_ID = "hummingbotfound"
MAX_ORDER_ID_LEN = 32

DOMAIN = EXCHANGE_NAME

PERPETUAL_BASE_URL = "https://api-cloud-v2.bitmart.com"
PERPETUAL_WS_URL = "wss://openapi-ws-v2.bitmart.com"

SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 20
PUBLIC_WS_ENDPOINT = "/api?protocol=1.1"
PRIVATE_WS_ENDPOINT = "/user?protocol=1.1"

TIME_IN_FORCE_GTC = 1  # Good till cancelled
TIME_IN_FORCE_FOK = 2  # Fill or kill
TIME_IN_FORCE_IOC = 3  # Immediate or cancel
TIME_IN_FORCE_MAKER_ONLY = 4  # Good Till Crossing

# Public API v2 Endpoints
SNAPSHOT_REST_URL = "/contract/public/depth"  # 12 times / 2 sec
EXCHANGE_INFO_URL = "/contract/public/details"  # 12 times / 2 sec
FUNDING_INFO_URL = "/contract/public/funding-rate"  # 12 times / 2 sec
SERVER_TIME_PATH_URL = "/system/time"  # 10 times / 2 sec

# Private API v1 Endpoints
SUBMIT_ORDER_URL = "/contract/private/submit-order"  # 24 times / 2 sec
ORDER_DETAILS = "/contract/private/order"  # 50 times / 2 sec
CANCEL_ORDER_URL = "/contract/private/cancel-order"  # 40 times / 2 sec
ACCOUNT_TRADE_LIST_URL = "/contract/private/trades"  # 6 times / 2 sec
SET_LEVERAGE_URL = "/contract/private/submit-leverage"  # 24 times / 2 sec
GET_INCOME_HISTORY_URL = "/contract/private/transaction-history"  # 6 times / 2 sec

# Private API v2 Endpoints
ASSETS_DETAIL = "/contract/private/assets-detail"  # 12 times / 2 sec
POSITION_INFORMATION_URL = "/contract/private/position"  # 6 times / 2 sec

# Public WS channels
TRADE_STREAM_CHANNEL = "futures/trade"
FUNDING_INFO_CHANNEL = "futures/fundingRate"
TICKERS_CHANNEL = "futures/ticker"
ORDER_BOOK_CHANNEL = "futures/depthIncrease50"
ORDER_BOOK_SPEED = "200ms"

# Private WS channels
WS_POSITIONS_CHANNEL = "futures/position"
WS_ORDERS_CHANNEL = "futures/order"
WS_ACCOUNT_CHANNEL = "futures/asset:USDT"

# Funding Settlement Time Span
FUNDING_SETTLEMENT_DURATION = (0, 30)  # seconds before snapshot, seconds after snapshot

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS_1MIN = "ORDERS_1MIN"
ORDERS_1SEC = "ORDERS_1SEC"

HEARTBEAT_TIME_INTERVAL = 30.0

# Rate Limit time intervals
RATE_LIMITS = [
    # Weight Limits for individual endpoints
    RateLimit(limit_id=SNAPSHOT_REST_URL, limit=12, time_interval=2),
    RateLimit(limit_id=EXCHANGE_INFO_URL, limit=12, time_interval=2),
    RateLimit(limit_id=FUNDING_INFO_URL, limit=12, time_interval=2),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=10, time_interval=2),
    RateLimit(limit_id=SUBMIT_ORDER_URL, limit=24, time_interval=2),
    RateLimit(limit_id=ORDER_DETAILS, limit=50, time_interval=2),
    RateLimit(limit_id=CANCEL_ORDER_URL, limit=40, time_interval=2),
    RateLimit(limit_id=ACCOUNT_TRADE_LIST_URL, limit=6, time_interval=2),
    RateLimit(limit_id=SET_LEVERAGE_URL, limit=24, time_interval=2),
    RateLimit(limit_id=GET_INCOME_HISTORY_URL, limit=6, time_interval=2),
    RateLimit(limit_id=ASSETS_DETAIL, limit=12, time_interval=2),
    RateLimit(limit_id=POSITION_INFORMATION_URL, limit=6, time_interval=2),
]

CODE_OK = 1000
ORDER_NOT_EXIST_ERROR_CODE = 40035
ORDER_NOT_EXIST_MESSAGE = "The order is not exist"
UNKNOWN_ORDER_ERROR_CODE = 40037
UNKNOWN_ORDER_MESSAGE = "The order id is not exist"
