from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

# Base API & WS URLs
LBANK_REST_URL = "https://api.lbkex.com/"
LBANK_WSS_URL = "wss://www.lbkex.net/ws/V2/"

API_VERSION = "v2"

LBANK_ORDER_BOOK_SNAPSHOT_DEPTH = 60

# Public REST Endpoints
LBANK_GET_TIMESTAMP_PATH_URL = "/timestamp.do"  # {"timestamp":1568269063244}
LBANK_ORDER_BOOK_PATH_URL = "/depth.do"
LBANK_TRADING_PAIRS_PATH_URL = "/accuracy.do"
LBANK_CURRENT_MARKET_DATA_PATH_URL = "/ticker/24hr.do"

# Private REST Endpoints
LBANK_CREATE_ORDER_PATH_URL = "/create_order.do"
LBANK_CANCEL_ORDER_PATH_URL = "/cancel_clientOrders.do"
LBANK_CREATE_LISTENING_KEY_PATH_URL = "/subscribe/get_key.do"
LBANK_REFRESH_LISTENING_KEY_PATH_URL = "/subscribe/refresh_key.do"
LBANK_USER_ASSET_PATH_URL = "/user_info.do"
LBANK_ORDER_UPDATES_PATH_URL = "/orders_info.do"
LBANK_TRADE_UPDATES_PATH_URL = "/order_transaction_detail.do"

# Public WS Channels
LBANK_ORDER_BOOK_DEPTH_CHANNEL = "depth"
LBANK_ORDER_BOOK_TRADE_CHANNEL = "trade"
LBANK_PING_RESPONSE = "ping"
LBANK_WS_PING_REQUEST_INTERVAL = 15

LBANK_ORDER_BOOK_DEPTH_CHANNEL_DEPTH = "50"

# Private WS Channels
LBANK_USER_ORDER_UPDATE_CHANNEL = "orderUpdate"
LBANK_USER_BALANCE_UPDATE_CHANNEL = "assetUpdate"

LBANK_LISTEN_KEY_EXPIRY_DURATION = 60 * 60 * 1e3  # 60 mins(milliseconds)

LBANK_LISTEN_KEY_KEEP_ALIVE_INTERVAL = int(LBANK_LISTEN_KEY_EXPIRY_DURATION // 2)

# Order Status
ORDER_STATUS = {
    -1: OrderState.CANCELED,
    0: OrderState.OPEN,
    1: OrderState.PARTIALLY_FILLED,
    2: OrderState.FILLED,
    3: OrderState.CANCELED,  # Partially Filled and Cancelled
    4: OrderState.PENDING_CANCEL
}

LBANK_AUTH_METHODS = [
    "RSA", "HmacSHA256"
]

# Misc Information
MAX_ID_LEN = 50
CLIENT_ID_PREFIX = "HBOT-"

LBANK_ORDER_LIMITS = 500  # per 10 seconds
LBANK_GLOBAL_LIMITS = 200  # per 10 seconds

TEN_SECONDS = 10

# Rate Limits
RATE_LIMITS = [
    # Individual endpoints
    RateLimit(limit_id=LBANK_CREATE_ORDER_PATH_URL, limit=LBANK_ORDER_LIMITS, time_interval=TEN_SECONDS),
    RateLimit(limit_id=LBANK_CANCEL_ORDER_PATH_URL, limit=LBANK_ORDER_LIMITS, time_interval=TEN_SECONDS),
    RateLimit(limit_id=LBANK_ORDER_BOOK_PATH_URL, limit=LBANK_GLOBAL_LIMITS, time_interval=TEN_SECONDS),
    RateLimit(limit_id=LBANK_CREATE_LISTENING_KEY_PATH_URL, limit=LBANK_GLOBAL_LIMITS, time_interval=TEN_SECONDS),
    RateLimit(limit_id=LBANK_REFRESH_LISTENING_KEY_PATH_URL, limit=LBANK_GLOBAL_LIMITS, time_interval=TEN_SECONDS),
    RateLimit(limit_id=LBANK_USER_ASSET_PATH_URL, limit=LBANK_GLOBAL_LIMITS, time_interval=TEN_SECONDS),
    RateLimit(limit_id=LBANK_CURRENT_MARKET_DATA_PATH_URL, limit=LBANK_GLOBAL_LIMITS, time_interval=TEN_SECONDS),
    RateLimit(limit_id=LBANK_TRADING_PAIRS_PATH_URL, limit=LBANK_GLOBAL_LIMITS, time_interval=TEN_SECONDS),
    RateLimit(limit_id=LBANK_GET_TIMESTAMP_PATH_URL, limit=LBANK_GLOBAL_LIMITS, time_interval=TEN_SECONDS),
    RateLimit(limit_id=LBANK_ORDER_UPDATES_PATH_URL, limit=LBANK_GLOBAL_LIMITS, time_interval=TEN_SECONDS),
    RateLimit(limit_id=LBANK_TRADE_UPDATES_PATH_URL, limit=LBANK_GLOBAL_LIMITS, time_interval=TEN_SECONDS),
]


# Error Codes
ERROR_CODES = {
    10000: "Internal error",
    10001: "The required parameters can not be empty",
    10002: "Validation Failed",
    10003: "Invalid parameter",
    10004: "Request too frequent",
    10005: "Secret key does not exist",
    10006: "User does not exist",
    10007: "Invalid signature",
    10008: "Invalid Trading Pair",
    10009: "Price and/or Amount are required for limit order",
    10010: "Price and/or Amount must less than minimum require",
    10013: "The amount is too small",
    10014: "Insufficient amount of money in account",
    10015: "Invalid order type",
    10016: "Insufficient account balance",
    10017: "Server Error",
    10018: "Page size should be between 1 and 50",
    10019: "Cancel NO more than 3 orders in one request",
    10020: "Volume < 0.001",
    10021: "Price < 0.01",
    10022: "Invalid authorization",
    10023: "Market Order is not supported yet",
    10024: "User cannot trade on this pair",
    10025: "Order has been filled",
    10026: "Order has been cancelld",
    10027: "Order is cancelling",
    10028: "Wrong query time",
    10029: "'from' is not in the query time",
    10030: "'from' do not match the transaction type of inqury",
    10031: "echostr length must be valid and length must be from 30 to 40",
    10033: "Failed to create order",
    10036: "customID duplicated",
    10100: "Has no privilege to withdraw",
    10101: "Invalid fee rate to withdraw",
    10102: "Too little to withdraw",
    10103: "Exceed daily limitation of withdraw",
    10104: "Cancel was rejected",
    10105: "Request has been cancelled",
    10106: "None trade time",
    10107: "Start price exception",
    10108: "can not create order",
    10109: "wallet address is not mapping",
    10110: "transfer fee is not mapping",
    10111: "mount > 0",
    10112: "fee is too lower",
    10113: "transfer fee is 0",
    10600: "intercepted by replay attacks filter, check timestamp",
    10601: "Interface closed unavailable",
    10701: "invalid asset code",
    10702: "not allowed deposit",
    10066: "Please check the chain name",
}
