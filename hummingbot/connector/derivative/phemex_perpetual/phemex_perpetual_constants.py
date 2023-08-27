import sys

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "phemex_perpetual"
MAX_ORDER_ID_LEN = 40

DEFAULT_DOMAIN = ""
TESTNET_DOMAIN = "phemex_perpetual_testnet"

BASE_URLS = {
    DEFAULT_DOMAIN: "https://api.phemex.com",
    TESTNET_DOMAIN: "https://testnet-api.phemex.com",
}

WSS_URLS = {
    DEFAULT_DOMAIN: "wss://phemex.com",
    TESTNET_DOMAIN: "wss://testnet.phemex.com",
}

PUBLIC_WS_ENDPOINT = "/ws"
PRIVATE_WS_ENDPOINT = "/ws"

WS_HEARTBEAT = 5  # https://phemex-docs.github.io/#heartbeat

COLLATERAL_TOKEN = "USDT"

# Public API Endpoints
SNAPSHOT_REST_URL = "/md/v2/orderbook"
TICKER_PRICE_URL = "/md/v2/ticker/24hr"
TICKER_PRICE_CHANGE_URL = "/exchange/public/md/v2/kline/last"
SERVER_TIME_PATH_URL = "/public/time"
MARK_PRICE_URL = TICKER_PRICE_URL
EXCHANGE_INFO_URL = "/public/products"

# Private API Endpoints
ACCOUNT_INFO = "/g-accounts/accountPositions"
PLACE_ORDERS = "/g-orders"
CANCEL_ORDERS = "/g-orders/cancel"
CANCEL_ALL_ORDERS = "/g-orders/all"
GET_ORDERS = "/api-data/g-futures/orders/by-order-id"
GET_TRADES = "/api-data/g-futures/trades"
POSITION_INFO = "/g-accounts/accountPositions"
POSITION_MODE = "/g-positions/switch-pos-mode-sync"
POSITION_LEVERAGE = "/g-positions/leverage"
USER_TRADE = "/exchange/order/v2/tradingList"
FUNDING_PAYMENT = "/api-data/g-futures/funding-fees"


# Funding Settlement Time Span
FUNDING_SETTLEMENT_DURATION = (0, 30)  # seconds before snapshot, seconds after snapshot


# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
API_CONTRACT_GENERAL_LIMIT = "API_CONTRACT_GENERAL_LIMIT"
WSS_CONNECTION_LIMIT_ID = "phemexWSSConnectionLimitID"
WSS_MESSAGE_LIMIT_ID = "phemexWSSMessageLimitID"

DIFF_STREAM_METHOD = "orderbook_p.subscribe"
TRADE_STREAM_METHOD = "trade_p.subscribe"
FUNDING_INFO_STREAM_METHOD = "perp_market24h_pack_p.subscribe"
HEARTBEAT_TIME_INTERVAL = 5.0

# Rate Limit time intervals
ONE_HOUR = 3600
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

NO_LIMIT = sys.maxsize


RATE_LIMITS = [
    # Pool Limits
    RateLimit(limit_id=REQUEST_WEIGHT, limit=100, time_interval=ONE_MINUTE),
    RateLimit(limit_id=API_CONTRACT_GENERAL_LIMIT, limit=500, time_interval=ONE_MINUTE),
    # WSS rate limits
    RateLimit(limit_id=WSS_CONNECTION_LIMIT_ID, limit=NO_LIMIT, time_interval=ONE_SECOND),
    RateLimit(limit_id=WSS_MESSAGE_LIMIT_ID, limit=NO_LIMIT, time_interval=ONE_SECOND),
    # Weight Limits for individual endpoints
    RateLimit(
        limit_id=SNAPSHOT_REST_URL,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT)],
    ),
    RateLimit(
        limit_id=TICKER_PRICE_URL,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT)],
    ),
    RateLimit(
        limit_id=TICKER_PRICE_CHANGE_URL,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        weight=10,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT)],
    ),
    RateLimit(
        limit_id=SERVER_TIME_PATH_URL,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT)],
    ),
    RateLimit(
        limit_id=MARK_PRICE_URL,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT)],
    ),
    RateLimit(
        limit_id=EXCHANGE_INFO_URL,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT)],
    ),
    RateLimit(
        limit_id=ACCOUNT_INFO,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(API_CONTRACT_GENERAL_LIMIT)],
    ),
    RateLimit(
        limit_id=PLACE_ORDERS,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(API_CONTRACT_GENERAL_LIMIT)],
    ),
    RateLimit(
        limit_id=CANCEL_ORDERS,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(API_CONTRACT_GENERAL_LIMIT)],
    ),
    RateLimit(
        limit_id=CANCEL_ALL_ORDERS,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(API_CONTRACT_GENERAL_LIMIT)],
    ),
    RateLimit(
        limit_id=GET_ORDERS,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(API_CONTRACT_GENERAL_LIMIT)],
    ),
    RateLimit(
        limit_id=GET_TRADES,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(API_CONTRACT_GENERAL_LIMIT)],
    ),
    RateLimit(
        limit_id=POSITION_INFO,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(API_CONTRACT_GENERAL_LIMIT)],
    ),
    RateLimit(
        limit_id=POSITION_MODE,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(API_CONTRACT_GENERAL_LIMIT)],
    ),
    RateLimit(
        limit_id=POSITION_LEVERAGE,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(API_CONTRACT_GENERAL_LIMIT)],
    ),
    RateLimit(
        limit_id=USER_TRADE,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(API_CONTRACT_GENERAL_LIMIT)],
    ),
    RateLimit(
        limit_id=FUNDING_PAYMENT,
        limit=NO_LIMIT,
        time_interval=ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(API_CONTRACT_GENERAL_LIMIT)],
    ),
]

# Order Statuses
ORDER_STATE = {
    "Created": OrderState.PENDING_CREATE,
    "Init": OrderState.PENDING_CREATE,
    "New": OrderState.OPEN,
    "PartiallyFilled": OrderState.PARTIALLY_FILLED,
    "Filled": OrderState.FILLED,
    "Canceled": OrderState.CANCELED,
    "Rejected": OrderState.FAILED,
}

SUCCESSFUL_RETURN_CODE = 0
ORDER_NOT_FOUND_ERROR_CODE = 10002
ORDER_NOT_FOUND_ERROR_MESSAGE = "OM_ORDER_NOT_FOUND"
