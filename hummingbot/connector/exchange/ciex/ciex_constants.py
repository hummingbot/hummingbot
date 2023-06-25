import sys

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

HBOT_BROKER_ID = ""
MAX_ORDER_ID_LEN = 32

DEFAULT_DOMAIN = ""
CIEX_BASE_URL = "https://openapi.ci-ex.com/sapi/v1/"
CIEX_WS_URL = "wss://ws.ci-ex.com/kline-api/ws"

MAX_ORDERS_PER_BATCH_CANCEL = 10

INVALID_TIMESTAMP_ERROR_CODE = "-1021"
ORDER_DOES_NOT_EXIST_ERROR_CODE = "-2013"
INVALID_API_KEY_ERROR_CODE = "-2015"
ORDER_NOT_EXIST_MESSAGE = "Order does not exist"

# Public endpoints
CIEX_TIME_PATH = "time"
CIEX_PING_PATH = "ping"
CIEX_SYMBOLS_PATH = "symbols"
CIEX_TICKER_PATH = "ticker"
CIEX_DEPTH_PATH = "depth"

# Private endpoints
CIEX_ORDER_PATH = "order"
CIEX_CANCEL_ORDER_PATH = "cancel"
CIEX_BATCH_CANCEL_ORDERS_PATH = "batchCancel"
CIEX_ORDER_FILLS_PATH = "myTrades"
CIEX_ACCOUNT_INFO_PATH = "account"

# WebSocket
WS_PUBLIC_TRADES_CHANNEL = "market_{}_trade_ticker"
WS_FULL_DEPTH_CHANNEL = "market_{}_depth_step0"

NO_LIMIT = sys.maxsize
WS_CONNECTION_LIMIT_ID = "CiexWSConnection"
WS_REQUEST_LIMIT_ID = "CiexWSRequest"
CIEX_ORDER_STATUS_LIMIT_ID = "OrderGetStatusLimitId"
CIEX_ORDER_CREATION_LIMIT_ID = "OrderCreationLimitId"

RATE_LIMITS = [
    RateLimit(limit_id=WS_CONNECTION_LIMIT_ID, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=WS_REQUEST_LIMIT_ID, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=CIEX_TIME_PATH, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=CIEX_PING_PATH, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=CIEX_SYMBOLS_PATH, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=CIEX_TICKER_PATH, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=CIEX_DEPTH_PATH, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=CIEX_ACCOUNT_INFO_PATH, limit=20, time_interval=2),
    RateLimit(limit_id=CIEX_ORDER_STATUS_LIMIT_ID, limit=20, time_interval=2),
    RateLimit(limit_id=CIEX_ORDER_CREATION_LIMIT_ID, limit=100, time_interval=2),
    RateLimit(limit_id=CIEX_CANCEL_ORDER_PATH, limit=100, time_interval=2),
    RateLimit(limit_id=CIEX_BATCH_CANCEL_ORDERS_PATH, limit=50, time_interval=2),
    RateLimit(limit_id=CIEX_ORDER_FILLS_PATH, limit=20, time_interval=2),
]

# Partially filled status appears twice because in the API doc it is presented as "PARTIALLY_FILLED" but in reality
# the exchange is sending it as "PART_FILLED"
NEW_STATUS = "NEW"
FILLED_STATUS = "FILLED"
PARTIALLY_FILLED_STATUS = "PARTIALLY_FILLED"
PART_FILLED_STATUS = "PART_FILLED"
CANCELED_STATUS = "CANCELED"
PENDING_CANCEL_STATUS = "PENDING_CANCEL"
REJECTED_STATUS = "REJECTED"

ORDER_STATE = {
    NEW_STATUS: OrderState.OPEN,
    FILLED_STATUS: OrderState.FILLED,
    PARTIALLY_FILLED_STATUS: OrderState.PARTIALLY_FILLED,
    PART_FILLED_STATUS: OrderState.PARTIALLY_FILLED,
    CANCELED_STATUS: OrderState.CANCELED,
    PENDING_CANCEL_STATUS: OrderState.PENDING_CANCEL,
    REJECTED_STATUS: OrderState.FAILED,
}
