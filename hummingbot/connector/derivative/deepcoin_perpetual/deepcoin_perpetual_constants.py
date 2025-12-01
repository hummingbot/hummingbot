from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionMode
from hummingbot.core.data_type.in_flight_order import OrderState

# Exchange Info
EXCHANGE_NAME = "deepcoin_perpetual"
DEFAULT_DOMAIN = "deepcoin_perpetual_main"

# Broker ID
HBOT_BROKER_ID = "Hummingbot"

# Order ID Configuration
MAX_ORDER_ID_LEN = 32

# REST URLs
REST_URLS = {
    "deepcoin_perpetual_main": "https://api.deepcoin.com",
    "deepcoin_perpetual_testnet": "https://test-api.goodtest.cc"
}

# WebSocket URLs
WSS_PUBLIC_URLS = {
    "deepcoin_perpetual_main": "wss://stream.deepcoin.com/streamlet/trade/public/swap?platform=api",
    "deepcoin_perpetual_testnet": "wss://test-wss.goodtest.cc/streamlet/trade/public/swap?platform=api"
}
# WSS_PRIVATE_URLS = {
#     "deepcoin_perpetual_main": "wss://stream.deepcoin.com/v1/private",
#     "deepcoin_perpetual_testnet": "wss://test-wss.goodtest.cc/v1/private"
# }

# User Stream WebSocket URLs (with listenKey parameter)
WSS_USER_STREAM_URLS = {
    "deepcoin_perpetual_main": "wss://stream.deepcoin.com/v1/private",
    "deepcoin_perpetual_testnet": "wss://test-wss.goodtest.cc/v1/private"
}

# WebSocket Configuration
WS_HEARTBEAT_TIME_INTERVAL = 10.0


# Order Type Mapping
ORDER_TYPE_MAP = {
    OrderType.LIMIT: "limit",
    OrderType.MARKET: "market",
    OrderType.LIMIT_MAKER: "post_only",
}

# Position Mode Mapping
POSITION_MODE_API_ONEWAY = 0
POSITION_MODE_API_HEDGE = 1
POSITION_MODE_MAP = {
    PositionMode.ONEWAY: POSITION_MODE_API_ONEWAY,
    PositionMode.HEDGE: POSITION_MODE_API_HEDGE,
}

# Public API Endpoints
SNAPSHOT_REST_URL = "/deepcoin/market/books"
TICKER_PRICE_URL = "/deepcoin/market/tickers"
INSTRUMENTID_INFO_URL = "deepcoin/market/instruments"
EXCHANGE_INFO_URL = "/deepcoin/market/instruments"
RECENT_TRADES_URL = "/deepcoin/market/trades"
PING_URL = "/deepcoin/market/ping"
MARK_PRICE_URL = "/deepcoin/market/markPrice"
FUNDING_INFO_URL = "/deepcoin/trade/funding-rate"
SERVER_TIME_PATH_URL = "/deepcoin/market/time"

# Private API Endpoints
CREATIVE_ORDER_URL = "/deepcoin/trade/order"
CANCEL_ALL_OPEN_ORDERS_URL = "/deepcoin/trade/swap/cancel-all"
CANCEL_OPEN_ORDERS_URL = "/deepcoin/trade/cancel-order"
ACCOUNT_TRADE_LIST_URL = "/deepcoin/trade/fills"
SET_LEVERAGE_URL = "/deepcoin/account/set-leverage"
GET_BILLS_DETAILS = "/deepcoin/account/bills"
GET_INCOME_HISTORY_URL = "/deepcoin/trade/income"
CHANGE_POSITION_MODE_URL = "/deepcoin/trade/positionMode"
ACTIVE_ORDER_URL = "/deepcoin/trade/orderByID"
REST_USER_TRADE_RECORDS = "/deepcoin/trade/orders-history"

# Account and Position Endpoints
ACCOUNT_INFO_URL = "/deepcoin/account/balances"
POSITION_INFORMATION_URL = "/deepcoin/account/positions"

# User Stream Endpoints
USER_STREAM_ENDPOINT = "/deepcoin/listenkey/acquire"
USER_STREAM_EXTEND_ENDPOINT = "/deepcoin/listenkey/extend"

# WebSocket Event Types
DIFF_EVENT_TYPE = "PMO"
TRADE_EVENT_TYPE = "PMT"
ORDER_UPDATE_EVENT_TYPE = "orderUpdate"
POSITION_UPDATE_EVENT_TYPE = "positionUpdate"
BALANCE_UPDATE_EVENT_TYPE = "balanceUpdate"


# Position Side
POSITION_SIDE_LONG = "long"
POSITION_SIDE_SHORT = "short"
# POSITION_SIDE_BOTH = "both"

# Position Mode
POSITION_MODE_ONE_WAY = "one_way"
POSITION_MODE_HEDGE = "hedge"

# Rate Limit Types
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS = "ORDERS"
ORDERS_24HR = "ORDERS_24HR"
RAW_REQUESTS = "RAW_REQUESTS"

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 1000

RATE_LIMITS = [
    RateLimit(
        limit_id=SNAPSHOT_REST_URL,
        limit=5,
        time_interval=1,
    ),
    RateLimit(
        limit_id=TICKER_PRICE_URL,
        limit=5,
        time_interval=1,
    ),
    RateLimit(
        limit_id=INSTRUMENTID_INFO_URL,
        limit=5,
        time_interval=1,
    ),
    RateLimit(
        limit_id=EXCHANGE_INFO_URL,
        limit=5,
        time_interval=1,
    ),
    RateLimit(
        limit_id=RECENT_TRADES_URL,
        limit=1,
        time_interval=1,
    ),
    RateLimit(
        limit_id=FUNDING_INFO_URL,
        limit=5,
        time_interval=1,
    ),
    RateLimit(
        limit_id=PING_URL,
        limit=5,
        time_interval=1,
    ),
    RateLimit(
        limit_id=SERVER_TIME_PATH_URL,
        limit=5,
        time_interval=1,
    ),
    RateLimit(
        limit_id=CREATIVE_ORDER_URL,
        limit=1,
        time_interval=1,
    ),
    RateLimit(
        limit_id=CANCEL_ALL_OPEN_ORDERS_URL,
        limit=1,
        time_interval=1,
    ),
    RateLimit(
        limit_id=CANCEL_OPEN_ORDERS_URL,
        limit=1,
        time_interval=1,
    ),
    RateLimit(
        limit_id=ACCOUNT_TRADE_LIST_URL,
        limit=1,
        time_interval=1,
    ),
    RateLimit(
        limit_id=SET_LEVERAGE_URL,
        limit=10,
        time_interval=1,
    ),
    RateLimit(
        limit_id=CHANGE_POSITION_MODE_URL,
        limit=1,
        time_interval=1,
    ),
    RateLimit(
        limit_id=ACCOUNT_INFO_URL,
        limit=1,
        time_interval=1,
    ),
    RateLimit(
        limit_id=POSITION_INFORMATION_URL,
        limit=1,
        time_interval=1,
    ),
    RateLimit(
        limit_id=USER_STREAM_ENDPOINT,
        limit=1,
        time_interval=1,
    ),
    RateLimit(
        limit_id=USER_STREAM_EXTEND_ENDPOINT,
        limit=1,
        time_interval=1,
    ),
]

# Error codes
ORDER_NOT_EXIST_ERROR_CODE = 40001
ORDER_NOT_EXIST_MESSAGE = "Order does not exist"
UNKNOWN_ORDER_ERROR_CODE = 40002
UNKNOWN_ORDER_MESSAGE = "Unknown order sent"
INSUFFICIENT_BALANCE_ERROR_CODE = 40003
INSUFFICIENT_BALANCE_MESSAGE = "Insufficient balance"
INVALID_LEVERAGE_ERROR_CODE = 40004
INVALID_LEVERAGE_MESSAGE = "Invalid leverage"


RET_CODE_OK = "0"

# Order Status
ORDER_STATE = {
    "live": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "canceled": OrderState.CANCELED,
}

WS_ORDER_STATE = {
    "1": OrderState.FILLED,
    "2": OrderState.PARTIALLY_FILLED,
    "3": OrderState.FILLED,
    "4": OrderState.OPEN,
    "5": OrderState.CANCELED,
}

WS_ORDERS_CHANNEL = "PushOrder"
WS_TRADES_CHANNEL = "PushTrade"
WS_POSITIONS_CHANNEL = "PushPosition"
WS_ACCOUNT_CHANNEL = "PushAccountDetail"


FUNDING_PAYMENT_TYPE = "7"
