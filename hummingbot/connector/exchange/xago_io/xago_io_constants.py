# A single source of truth for constant variables related to the exchange

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "xago_io"
DOMAIN = ""

HBOT_ORDER_ID_PREFIX = "HB-XA-"
MAX_ORDER_ID_LEN = 32

WSS_PING_INTERVAL = 20

# PRODUCTION ENDPOINTS
IDENTITY_REST_URL = "https://identity-api.xago.io/v1/"
EXCHANGE_REST_URL = "https://exchange-api.xago.io/v1/"
WEBSOCKET_URL = "wss://stream.xago.io/account"
POLICY_ID = "5eb29c307df9090021eed488"

# STAGING ENDPOINTS
# IDENTITY_REST_URL = "https://test-api.xago.io:9000/v1/"
# EXCHANGE_REST_URL = "https://test-api.xago.io:8085/v1/"
# WEBSOCKET_URL = "wss://test-stream.xago.io/account"
# POLICY_ID = "5e2585a474b0e90012ce8ff1"

# LOCAL ENDPOINTS
# IDENTITY_REST_URL = "http://localhost:8082/v1/"
# EXCHANGE_REST_URL = "http://localhost:8085/v1/"
# WEBSOCKET_URL = "ws://localhost:3000/account"
# POLICY_ID = "5e2585a474b0e90012ce8ff1"

# BEARER TOKEN
ACCESS_TOKEN = ""

# REST API PATHS
CANCEL_ORDER_PATH_URL = "/orders/cancellation?orderId="
CREATE_ORDER_PATH_URL = "orders"
GET_ACCOUNT_SUMMARY_PATH_URL = "wallet"
GET_ACCOUNT_TOKEN = "login/"
GET_FX_RATES = "prices/current"
GET_OPEN_ORDERS_PATH_URL = "orders?status=pending&status=partially-filled&currencyPair="
GET_ORDER_BOOK_PATH_URL = "orderbook?currencyPair="
GET_ORDER_DETAIL_PATH_URL = "orders?orderId="
GET_ORDER_FILLS_PATH_URL = "orders"
GET_TICKER_PATH_URL = "prices/ticker"
GET_TRADING_RULES_PATH_URL = "/currencypairs"

# Order States
ORDER_STATE = {
    "CANCELLED": OrderState.CANCELED,
    "CANCELLING": OrderState.CANCELED,
    "ERROR": OrderState.CANCELED,
    "FAILED": OrderState.CANCELED,
    "FILLED": OrderState.FILLED,
    "PARTIALLY-FILLED": OrderState.PARTIALLY_FILLED,
    "PENDING": OrderState.OPEN,
    "SUCCESS": OrderState.FILLED,
}

# WEBSOCKET STREAM NAMES
BALANCE_STREAM = "balance"
INFO_STREAM = "info"
ORDER_BOOK_DIFF_STREAM = "ob-inc"
ORDER_BOOK_SNAPSHOT_STREAM = "ob-snap"
ORDER_STREAM = "order"
TRADE_STREAM = "trade"
# RATE LIMITS

RATE_LIMITS = [
    RateLimit(limit_id=CANCEL_ORDER_PATH_URL, limit=1000, time_interval=0.1),
    RateLimit(limit_id=CREATE_ORDER_PATH_URL, limit=1000, time_interval=0.1),
    RateLimit(limit_id=GET_ACCOUNT_SUMMARY_PATH_URL, limit=1000, time_interval=0.1),
    RateLimit(limit_id=GET_ACCOUNT_TOKEN, limit=1000, time_interval=0.1),
    RateLimit(limit_id=GET_FX_RATES, limit=1000, time_interval=1),
    RateLimit(limit_id=GET_OPEN_ORDERS_PATH_URL, limit=1000, time_interval=0.1),
    RateLimit(limit_id=GET_ORDER_BOOK_PATH_URL, limit=1000, time_interval=1),
    RateLimit(limit_id=GET_ORDER_DETAIL_PATH_URL, limit=1000, time_interval=0.1),
    RateLimit(limit_id=GET_TICKER_PATH_URL, limit=1000, time_interval=1),
    RateLimit(limit_id=GET_TRADING_RULES_PATH_URL, limit=1000, time_interval=1),
]

API_REASONS = {
    0: "Success",
    10001: "Malformed request, (E.g. not using application/json for REST)",
    10002: "Not authenticated, or key/signature incorrect",
    10003: "IP address not whitelisted",
    10004: "Missing required fields",
    10005: "Disallowed based on user tier",
    10006: "Requests have exceeded rate limits",
    10007: "Nonce value differs by more than 30 seconds from server",
    10008: "Invalid method specified",
    10009: "Invalid date range",
    20001: "Duplicated record",
    20002: "Insufficient balance",
    30003: "Invalid instrument_name specified",
    30004: "Invalid side specified",
    30005: "Invalid type specified",
    30006: "Price is lower than the minimum",
    30007: "Price is higher than the maximum",
    30008: "Quantity is lower than the minimum",
    30009: "Quantity is higher than the maximum",
    30010: "Required argument is blank or missing",
    30013: "Too many decimal places for Price",
    30014: "Too many decimal places for Quantity",
    30016: "The notional amount is less than the minimum",
    30017: "The notional amount exceeds the maximum",
}

ORDER_NOT_EXIST_ERROR_CODE = 404
ORDER_NOT_EXIST_MESSAGE = "Order does not exist"
UNKNOWN_ORDER_ERROR_CODE = 404
UNKNOWN_ORDER_MESSAGE = "Unknown order sent"
