import sys

from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState

CONNECTOR_NAME = "dexalot"

MAX_ORDER_CREATIONS_PER_BATCH = 10
MAX_ORDER_CANCELATIONS_PER_BATCH = 15
MAX_ID_HEX_DIGITS = 64
MAX_ID_BIT_COUNT = MAX_ID_HEX_DIGITS * 4
LOST_ORDER_COUNT_LIMIT = 10

DEFAULT_DOMAIN = "mainnet"

ORDERS_PATH = "/signed/orders"
BATCH_OPEN_ORDERS_PATH = "/trading/openorders/params"
EXECUTIONS_PATH = "/signed/executions"
WS_AUTH_PATH = "/auth/getwstoken"

BASE_PATH_URL = {
    "dexalot": "https://api.dexalot.com/privapi",
    "testnet": "api.dexalot-test.com/privapi"
}
WS_PATH_URL = {
    "dexalot": "wss://api.dexalot.com",
    "testnet": "wss://api.dexalot-test.com",
}

HEARTBEAT_TIME_INTERVAL = 30.0

GLOBAL_RATE_LIMIT_ID = "dexalotGlobalRateLimitID"
ORDERS_RATE_LIMIT_ID = "dexalotOrdersRateLimitID"
BATCH_OPEN_ORDERS_RATE_LIMIT_ID = "dexalotBatchOpenOrdersRateLimitID"
EXECUTIONS_RATE_LIMIT_ID = "dexalotExecutionsRateLimitID"
WS_AUTH_RATE_LIMIT_ID = "dexalotWSAuthRateLimitID"

WS_SUB_RATE_LIMIT_ID = "dexalotWSSubRateLimitID"

RATE_LIMITS = [
    RateLimit(limit_id=GLOBAL_RATE_LIMIT_ID, limit=10, time_interval=6),
    RateLimit(
        limit_id=ORDERS_RATE_LIMIT_ID,
        limit=sys.maxsize,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_RATE_LIMIT_ID, weight=1)],
    ),
    RateLimit(
        limit_id=BATCH_OPEN_ORDERS_RATE_LIMIT_ID,
        limit=sys.maxsize,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_RATE_LIMIT_ID, weight=1)],
    ),
    RateLimit(
        limit_id=EXECUTIONS_RATE_LIMIT_ID,
        limit=sys.maxsize,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_RATE_LIMIT_ID, weight=1)],
    ),
    RateLimit(
        limit_id=WS_AUTH_RATE_LIMIT_ID,
        limit=sys.maxsize,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_RATE_LIMIT_ID, weight=1)],
    ),
    RateLimit(
        limit_id=WS_SUB_RATE_LIMIT_ID,
        limit=sys.maxsize,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(limit_id=GLOBAL_RATE_LIMIT_ID, weight=1)],
    ),
]
ORDER_SIDE_MAP = bidict(
    {
        0: TradeType.BUY,
        1: TradeType.SELL
    }
)
ORDER_TYPE_MAP = bidict(
    {
        0: OrderType.MARKET,
        1: OrderType.LIMIT,
        2: OrderType.LIMIT_MAKER,
    }
)

HB_TO_DEXALOT_NUMERIC_STATUS_MAP = {
    OrderState.OPEN: 0,
    OrderState.FAILED: 1,
    OrderState.PARTIALLY_FILLED: 2,
    OrderState.FILLED: 3,
    OrderState.CANCELED: 4,
}
HB_TO_DEXALOT_STATUS_MAP = {
    OrderState.OPEN: "NEW",
    OrderState.FAILED: "REJECTED",
    OrderState.PARTIALLY_FILLED: "PARTIAL",
    OrderState.FILLED: "FILLED",
    OrderState.CANCELED: "CANCELED",
}
DEXALOT_TO_HB_NUMERIC_STATUS_MAP = {
    0: OrderState.OPEN,
    1: OrderState.FAILED,
    2: OrderState.PARTIALLY_FILLED,
    3: OrderState.FILLED,
    4: OrderState.CANCELED,
    6: OrderState.CANCELED,
    7: OrderState.FILLED,
}
DEXALOT_TO_HB_STATUS_MAP = {
    "NEW": OrderState.OPEN,
    "REJECTED": OrderState.FAILED,
    "PARTIAL": OrderState.PARTIALLY_FILLED,
    "FILLED": OrderState.FILLED,
    "CANCELED": OrderState.CANCELED,
    "KILLED": OrderState.FAILED,
    "CANCEL_REJECT": OrderState.FILLED,
}
