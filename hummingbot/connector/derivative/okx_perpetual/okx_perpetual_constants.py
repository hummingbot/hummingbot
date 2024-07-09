from hummingbot.core.data_type.common import OrderType, PositionMode
from hummingbot.core.data_type.in_flight_order import OrderState

# Init connector
EXCHANGE_NAME = "okx_perpetual"
REST_API_VERSION = "v5"
HBOT_BROKER_ID = "Hummingbot"
CLIENT_ID_PREFIX = "93027a12dac34fBC"
MAX_ID_LEN = 32

# -------------------------------------------
# BASE URLS
# -------------------------------------------
DEFAULT_DOMAIN = EXCHANGE_NAME
REST_URLS = {DEFAULT_DOMAIN: "https://www.okx.com"}

# -------------------------------------------
# DATA TYPES
# -------------------------------------------
POSITION_MODE_API_ONEWAY = "net_mode"
POSITION_MODE_API_HEDGE = "long_short_mode"
POSITION_MODE_MAP = {
    PositionMode.ONEWAY: POSITION_MODE_API_ONEWAY,
    PositionMode.HEDGE: POSITION_MODE_API_HEDGE,
}

ORDER_TYPE_MAP = {
    OrderType.LIMIT: "limit",
    OrderType.MARKET: "market",
    OrderType.LIMIT_MAKER: "post_only",
}

GET = "GET"
POST = "POST"
METHOD = "METHOD"
ENDPOINT = "ENDPOINT"

# Order Status
ORDER_STATE = {
    "live": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "canceled": OrderState.CANCELED,
    "mmp_canceled": OrderState.CANCELED,
}

FUNDING_PAYMENT_EXPENSE_SUBTYPE = "173"
FUNDING_PAYMENT_INCOME_SUBTYPE = "174"
FUNDING_PAYMENT_TYPE = "8"
# -------------------------------------------
# WEB SOCKET ENDPOINTS
# -------------------------------------------
WSS_PUBLIC_URLS = {DEFAULT_DOMAIN: f"wss://ws.okx.com:8443/ws/{REST_API_VERSION}/public"}
WSS_PRIVATE_URLS = {DEFAULT_DOMAIN: f"wss://ws.okx.com:8443/ws/{REST_API_VERSION}/private"}
WSS_BUSINESS_URLS = {DEFAULT_DOMAIN: f"wss://ws.okx.com:8443/ws/{REST_API_VERSION}/business"}

# WS CONFIG
SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 25
WS_PING_REQUEST = "ping"
WS_PONG_RESPONSE = "pong"

# API ORDER BOOK DATA SOURCE CHANNELS
WS_TRADES_CHANNEL = "trades"
WS_TRADES_ALL_CHANNEL = "trades-all"
WS_MARK_PRICE_CHANNEL = "mark-price"
WS_INDEX_TICKERS_CHANNEL = "index-tickers"
WS_FUNDING_INFO_CHANNEL = "funding-rate"
WS_ORDER_BOOK_400_DEPTH_100_MS_EVENTS_CHANNEL = "books"
WS_ORDER_BOOK_5_DEPTH_100_MS_EVENTS_CHANNEL = "books5"
WS_ORDER_BOOK_1_DEPTH_10_MS_EVENTS_CHANNEL = "bbo-tbt"
WS_INSTRUMENTS_INFO_CHANNEL = "instruments"

# USER STREAM DATA SOURCE CHANNELS
WS_ACCOUNT_CHANNEL = "account"
WS_BALANCE_AND_POSITIONS_CHANNEL = "balance_and_position"
WS_POSITIONS_CHANNEL = "positions"
WS_ORDERS_CHANNEL = "orders"

# -------------------------------------------
# WEB UTILS ENDPOINTS
# The structure is REST_url = {method: GET/POST, endpoint: /api/v5/...} since for the same endpoint you can have
# different methods. This is also useful for rate limit ids.
# -------------------------------------------
# REST API Public Endpoints
REST_LATEST_SYMBOL_INFORMATION = f"/api/{REST_API_VERSION}/market/tickers"
REST_ORDER_BOOK = f"/api/{REST_API_VERSION}/market/books"
REST_SERVER_TIME = f"/api/{REST_API_VERSION}/public/time"
REST_MARK_PRICE = f"/api/{REST_API_VERSION}/public/mark-price"
REST_INDEX_TICKERS = f"/api/{REST_API_VERSION}/market/index-tickers"
REST_GET_INSTRUMENTS = f"/api/{REST_API_VERSION}/public/instruments"

# REST API Private General Endpoints
REST_GET_WALLET_BALANCE = f"/api/{REST_API_VERSION}/account/balance"
REST_GET_ACCOUNT_CONFIG = f"/api/{REST_API_VERSION}/account/config"
REST_SET_POSITION_MODE = f"/api/{REST_API_VERSION}/account/set-position-mode"

# REST API Private Pair Specific Endpoints
REST_SET_LEVERAGE = f"/api/{REST_API_VERSION}/account/set-leverage"
REST_FUNDING_RATE_INFO = f"/api/{REST_API_VERSION}/public/funding-rate"
REST_GET_POSITIONS = f"/api/{REST_API_VERSION}/account/positions"
REST_PLACE_ACTIVE_ORDER = f"/api/{REST_API_VERSION}/trade/order"
REST_CANCEL_ACTIVE_ORDER = f"/api/{REST_API_VERSION}/trade/cancel-order"
REST_QUERY_ACTIVE_ORDER = REST_PLACE_ACTIVE_ORDER
REST_USER_TRADE_RECORDS = f"/api/{REST_API_VERSION}/trade/fills"
REST_BILLS_DETAILS = f"/api/{REST_API_VERSION}/account/bills"
REST_WS_LOGIN_PATH = "/users/self/verify"


# -------------------------------------------
# RET CODES
# -------------------------------------------

RET_CODE_OK = "0"

RET_CODE_TIMESTAMP_HEADER_MISSING = "50107"
RET_CODE_TIMESTAMP_HEADER_INVALID = "50112"
RET_CODE_PARAMS_ERROR = "51000"
RET_CODE_API_KEY_INVALID = "50111"
RET_CODE_INVALID_SIGNATURE = "50113"
RET_CODE_CANCEL_FAILED_BECAUSE_ORDER_NOT_EXISTS = "51603"
RET_CODE_ORDER_ALREADY_CANCELLED = "51401"
