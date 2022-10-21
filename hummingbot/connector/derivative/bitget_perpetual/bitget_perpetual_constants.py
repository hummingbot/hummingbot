from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionMode
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "bitget_perpetual"

DEFAULT_DOMAIN = ""

DEFAULT_TIME_IN_FORCE = "normal"

REST_URL = "https://api.bitget.com"
WSS_URL = "wss://ws.bitget.com/mix/v1/stream"

SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 20  # According to the documentation this has to be less than 30 seconds

ORDER_TYPE_MAP = {
    OrderType.LIMIT: "limit",
    OrderType.MARKET: "market",
}

POSITION_MODE_API_ONEWAY = "fixed"
POSITION_MODE_API_HEDGE = "crossed"
POSITION_MODE_MAP = {
    PositionMode.ONEWAY: POSITION_MODE_API_ONEWAY,
    PositionMode.HEDGE: POSITION_MODE_API_HEDGE,
}

SYMBOL_AND_PRODUCT_TYPE_SEPARATOR = "_"
USDT_PRODUCT_TYPE = "UMCBL"
USDC_PRODUCT_TYPE = "CMCBL"
USD_PRODUCT_TYPE = "DMCBL"
ALL_PRODUCT_TYPES = [USDT_PRODUCT_TYPE, USDC_PRODUCT_TYPE, USD_PRODUCT_TYPE]

# REST API Public Endpoints
LATEST_SYMBOL_INFORMATION_ENDPOINT = "/api/mix/v1/market/ticker"
QUERY_SYMBOL_ENDPOINT = "/api/mix/v1/market/contracts"
ORDER_BOOK_ENDPOINT = "/api/mix/v1/market/depth"
SERVER_TIME_PATH_URL = "/api/mix/v1/"
GET_LAST_FUNDING_RATE_PATH_URL = "/api/mix/v1/market/current-fundRate"
OPEN_INTEREST_PATH_URL = "/api/mix/v1/market/open-interest"
MARK_PRICE_PATH_URL = "/api/mix/v1/market/mark-price"

# REST API Private Endpoints
SET_LEVERAGE_PATH_URL = "/api/mix/v1/account/setLeverage"
GET_POSITIONS_PATH_URL = "/api/mix/v1/position/allPosition"
PLACE_ACTIVE_ORDER_PATH_URL = "/api/mix/v1/order/placeOrder"
CANCEL_ACTIVE_ORDER_PATH_URL = "/api/mix/v1/order/cancel-order"
CANCEL_ALL_ACTIVE_ORDERS_PATH_URL = "/api/mix/v1/order/cancel-batch-orders"
QUERY_ACTIVE_ORDER_PATH_URL = "/api/mix/v1/order/detail"
USER_TRADE_RECORDS_PATH_URL = "/api/mix/v1/order/fills"
GET_WALLET_BALANCE_PATH_URL = "/api/mix/v1/account/accounts"
SET_POSITION_MODE_URL = "/api/mix/v1/account/setMarginMode"
GET_FUNDING_FEES_PATH_URL = "/api/mix/v1/account/accountBill"

# Funding Settlement Time Span
FUNDING_SETTLEMENT_TIME_PATH_URL = "/api/mix/v1/market/funding-time"

# WebSocket Public Endpoints
WS_PING_REQUEST = "ping"
WS_PONG_RESPONSE = "pong"
WS_ORDER_BOOK_EVENTS_TOPIC = "books"
WS_TRADES_TOPIC = "trade"
WS_INSTRUMENTS_INFO_TOPIC = "tickers"
WS_AUTHENTICATE_USER_ENDPOINT_NAME = "login"
WS_SUBSCRIPTION_POSITIONS_ENDPOINT_NAME = "positions"
WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME = "orders"
WS_SUBSCRIPTION_WALLET_ENDPOINT_NAME = "account"

# Order Statuses
ORDER_STATE = {
    "new": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "full-fill": OrderState.FILLED,
    "partial-fill": OrderState.PARTIALLY_FILLED,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "canceled": OrderState.CANCELED,
    "cancelled": OrderState.CANCELED,
}

# Request error codes
RET_CODE_OK = "00000"
RET_CODE_PARAMS_ERROR = "40007"
RET_CODE_API_KEY_INVALID = "40006"
RET_CODE_AUTH_TIMESTAMP_ERROR = "40005"
RET_CODE_ORDER_NOT_EXISTS = "43025"
RET_CODE_API_KEY_EXPIRED = "40014"


RATE_LIMITS = [
    RateLimit(
        limit_id=LATEST_SYMBOL_INFORMATION_ENDPOINT,
        limit=20,
        time_interval=1,
    ),
    RateLimit(
        limit_id=QUERY_SYMBOL_ENDPOINT,
        limit=20,
        time_interval=1,
    ),
    RateLimit(
        limit_id=ORDER_BOOK_ENDPOINT,
        limit=20,
        time_interval=1,
    ),
    RateLimit(
        limit_id=SERVER_TIME_PATH_URL,
        limit=20,
        time_interval=1,
    ),
    RateLimit(
        limit_id=GET_LAST_FUNDING_RATE_PATH_URL,
        limit=20,
        time_interval=1,
    ),
    RateLimit(
        limit_id=OPEN_INTEREST_PATH_URL,
        limit=20,
        time_interval=1,
    ),
    RateLimit(
        limit_id=MARK_PRICE_PATH_URL,
        limit=20,
        time_interval=1,
    ),
    RateLimit(
        limit_id=FUNDING_SETTLEMENT_TIME_PATH_URL,
        limit=20,
        time_interval=1,
    ),
    RateLimit(
        limit_id=SET_LEVERAGE_PATH_URL,
        limit=5,
        time_interval=2,
    ),
    RateLimit(
        limit_id=GET_POSITIONS_PATH_URL,
        limit=5,
        time_interval=2,
    ),
    RateLimit(
        limit_id=PLACE_ACTIVE_ORDER_PATH_URL,
        limit=10,
        time_interval=1,
    ),
    RateLimit(
        limit_id=CANCEL_ACTIVE_ORDER_PATH_URL,
        limit=10,
        time_interval=1,
    ),
    RateLimit(
        limit_id=CANCEL_ALL_ACTIVE_ORDERS_PATH_URL,
        limit=10,
        time_interval=1,
    ),
    RateLimit(
        limit_id=QUERY_ACTIVE_ORDER_PATH_URL,
        limit=20,
        time_interval=1,
    ),
    RateLimit(
        limit_id=USER_TRADE_RECORDS_PATH_URL,
        limit=20,
        time_interval=2,
    ),
    RateLimit(
        limit_id=GET_WALLET_BALANCE_PATH_URL,
        limit=20,
        time_interval=2,
    ),
    RateLimit(
        limit_id=SET_POSITION_MODE_URL,
        limit=5,
        time_interval=1,
    ),
    RateLimit(
        limit_id=GET_FUNDING_FEES_PATH_URL,
        limit=10,
        time_interval=1,
    ),
]
