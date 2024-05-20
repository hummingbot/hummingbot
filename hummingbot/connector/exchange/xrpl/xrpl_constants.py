import sys

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState, OrderType

EXCHANGE_NAME = "xrpl"

DEFAULT_DOMAIN = "mainnet"
TESTNET_DOMAIN = "testnet"
DEVNET_DOMAIN = "devnet"


HBOT_ORDER_ID_PREFIX = "hbot"
MAX_ORDER_ID_LEN = 32

# Base URL
REST_URL = {"mainnet": "wss://xrplcluster.com/",
            "testnet": "wss://testnet.xrpl-labs.com/",
            "devnet": "wss://s.devnet.rippletest.net:51233/"}


# Order States
ORDER_STATE = {
    "open": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "partial_filled": OrderState.PARTIALLY_FILLED,
    "canceled": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
}

# Order Types
XRPL_ORDER_TYPE = {
    OrderType.LIMIT: 0,
    OrderType.LIMIT_MAKER: 65536,
    OrderType.MARKET: 131072,
}

# Order Side
SIDE_BUY = 0
SIDE_SELL = 1

# Market Order Max Slippage Percentage
MAX_SLIPPAGE_PERCENTAGE = 5

# Time in force
TIME_IN_FORCE_IOC = 0
TIME_IN_FORCE_GTC = 1
TIME_IN_FORCE_FOK = 2

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS = "ORDERS"
ORDERS_24HR = "ORDERS_24HR"
RAW_REQUESTS = "RAW_REQUESTS"

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 300

# Rate Limits
NO_LIMIT = sys.maxsize
RATE_LIMITS = [
    RateLimit(limit_id=REQUEST_WEIGHT, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=ORDERS, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=ORDERS_24HR, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=RAW_REQUESTS, limit=NO_LIMIT, time_interval=1),
    # Weighted Limits
    # RateLimit(limit_id=TICKER_BOOK_PATH_URL, limit=NO_LIMIT, time_interval=1),
    # RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=NO_LIMIT, time_interval=1),
    # RateLimit(limit_id=SNAPSHOT_LM_ID, limit=NO_LIMIT, time_interval=1),
    # RateLimit(limit_id=USER_STREAM_LM_ID, limit=NO_LIMIT, time_interval=1),
    # RateLimit(limit_id=PING_PATH_URL, limit=NO_LIMIT, time_interval=1),
    # RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=NO_LIMIT, time_interval=1),
    # RateLimit(limit_id=FILLS_PATH_URL, limit=NO_LIMIT, time_interval=1),
    # RateLimit(limit_id=ORDER_PATH_URL, limit=NO_LIMIT, time_interval=1),
    # RateLimit(limit_id=POST_ORDER_PATH_URL, limit=NO_LIMIT, time_interval=1),
]
