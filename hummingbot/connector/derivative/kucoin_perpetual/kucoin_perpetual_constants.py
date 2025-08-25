import sys

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionMode
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "kucoin_perpetual"

DEFAULT_DOMAIN = "kucoin_perpetual_main"

DEFAULT_TIME_IN_FORCE = "GTC"

REST_URLS = {"kucoin_perpetual_main": "https://api-futures.kucoin.com/"}
WSS_PUBLIC_URLS = {"kucoin_perpetual_main": "wss://stream.kucoin.com/realtime_public"}
WSS_PRIVATE_URLS = {"kucoin_perpetual_main": "wss://stream.kucoin.com/realtime_private"}
REST_API_VERSION = "api/v1"

HB_PARTNER_ID = "Hummingbot"
HB_PARTNER_KEY = "8fb50686-81a8-408a-901c-07c5ac5bd758"

MAX_ID_LEN = 40
SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 30

ONE_HOUR = 3600

WS_HEARTBEAT_TIME_INTERVAL = 30

ORDER_TYPE_MAP = {
    OrderType.LIMIT: "limit",
    OrderType.LIMIT_MAKER: "limit",
    OrderType.MARKET: "market",
}

POSITION_MODE_API_ONEWAY = "MergedSingle"
POSITION_MODE_API_HEDGE = "BothSide"
POSITION_MODE_MAP = {
    PositionMode.ONEWAY: POSITION_MODE_API_ONEWAY,
    PositionMode.HEDGE: POSITION_MODE_API_HEDGE,
}

# REST API Public Endpoints
QUERY_SYMBOL_ENDPOINT = f"{REST_API_VERSION}/contracts/active"
LATEST_SYMBOL_INFORMATION_ENDPOINT = f"{REST_API_VERSION}/ticker?symbol={{symbol}}"
ORDER_BOOK_ENDPOINT = f"{REST_API_VERSION}/level2/depth100?symbol={{symbol}}"
SERVER_TIME_PATH_URL = f"{REST_API_VERSION}/timestamp"
GET_LAST_FUNDING_RATE_PATH_URL = f"{REST_API_VERSION}/funding-rate/{{symbol}}/current"
GET_FUNDING_HISTORY_PATH_URL = f"{REST_API_VERSION}/funding-history?symbol={{symbol}}"
GET_CONTRACT_INFO_PATH_URL = f"{REST_API_VERSION}/contracts/{{symbol}}"

# REST API Private Endpoints
CREATE_ORDER_PATH_URL = f"{REST_API_VERSION}/orders"
CANCEL_ORDER_PATH_URL = f"{REST_API_VERSION}/orders/{{orderid}}"
QUERY_ORDER_BY_EXCHANGE_ORDER_ID_PATH_URL = f"{REST_API_VERSION}/orders/{{orderid}}"
QUERY_ORDER_BY_CLIENT_ORDER_ID_PATH_URL = f"{REST_API_VERSION}/orders/byClientOid?clientOid={{clientorderid}}"
GET_RISK_LIMIT_LEVEL_PATH_URL = f"{REST_API_VERSION}/contracts/risk-limit/{{symbol}}"
SET_LEVERAGE_PATH_URL = f"{REST_API_VERSION}/position/risk-limit-level/change"
GET_RECENT_FILLS_INFO_PATH_URL = f"{REST_API_VERSION}/recentFills"
GET_FILL_INFO_PATH_URL = f"{REST_API_VERSION}/fills?orderId={{orderid}}"
GET_WALLET_BALANCE_PATH_URL = f"{REST_API_VERSION}/account-overview?currency={{currency}}"
GET_POSITIONS_PATH_URL = f"{REST_API_VERSION}/positions"
QUERY_ACTIVE_ORDER_PATH_URL = f"{REST_API_VERSION}/orders?status=active"
QUERY_ALL_ORDER_PATH_URL = f"{REST_API_VERSION}/orders"

# Websocket
PUBLIC_WS_DATA_PATH_URL = f"{REST_API_VERSION}/bullet-public"
PRIVATE_WS_DATA_PATH_URL = f"{REST_API_VERSION}/bullet-private"

WS_PING_REQUEST = "ping"
WS_ORDER_BOOK_EVENTS_TOPIC = "/contractMarket/level2"
WS_TRADES_TOPIC = "/contractMarket/tradeOrders"
WS_INSTRUMENTS_INFO_TOPIC = "/contract/instrument"
WS_TICKER_INFO_TOPIC = "/contractMarket/ticker"
WS_WALLET_INFO_TOPIC = "/contractAccount/wallet"
WS_EXECUTION_DATA_TOPIC = "/contractMarket/execution"
WS_POSITION_CHANGE_TOPIC = "/contract/position"
WS_AUTHENTICATE_USER_ENDPOINT_NAME = "auth"
WS_SUBSCRIPTION_POSITIONS_ENDPOINT_NAME = "position.change"
WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME = "orderChange"
WS_SUBSCRIPTION_EXECUTIONS_ENDPOINT_NAME = "match"
WS_SUBSCRIPTION_WELCOME_MESSAGE = "welcome"
WS_ADJUST_RISK_LIMIT_MESSAGE = "position.adjustRiskLimit"

WS_SUBSCRIPTION_WALLET_ENDPOINT_NAME = "availableBalance.change"

WS_CONNECTION_LIMIT_ID = "WSConnection"
WS_CONNECTION_LIMIT = 30
WS_CONNECTION_TIME_INTERVAL = 20
WS_REQUEST_LIMIT_ID = "WSRequest"

# Order Statuses
ORDER_STATE = {
    "open": OrderState.OPEN,
    "done": OrderState.FILLED,
    "cancelExist": OrderState.CANCELED,
}

# Request error codes
RET_CODE_OK = "200000"
RET_CODE_PARAMS_ERROR = "100001"
RET_CODE_API_KEY_INVALID = "400001"
RET_CODE_ORDER_NOT_EXISTS = "20001"
RET_CODE_MODE_POSITION_NOT_EMPTY = "30082"
RET_CODE_MODE_NOT_MODIFIED = "300010"
RET_CODE_LEVERAGE_NOT_MODIFIED = "300016"
RET_CODE_POSITION_ZERO = "300009"
RET_CODE_AUTH_TIMESTAMP_ERROR = "400002"

NO_LIMIT = sys.maxsize
RATE_LIMITS = [
    RateLimit(WS_CONNECTION_LIMIT_ID, limit=WS_CONNECTION_LIMIT, time_interval=WS_CONNECTION_TIME_INTERVAL),
    RateLimit(WS_REQUEST_LIMIT_ID, limit=100, time_interval=10),
    RateLimit(limit_id=PUBLIC_WS_DATA_PATH_URL, limit=100, time_interval=10),
    RateLimit(limit_id=PRIVATE_WS_DATA_PATH_URL, limit=100, time_interval=10),
    RateLimit(limit_id=LATEST_SYMBOL_INFORMATION_ENDPOINT, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=QUERY_SYMBOL_ENDPOINT, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=ORDER_BOOK_ENDPOINT, limit=30, time_interval=3),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=SET_LEVERAGE_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=GET_LAST_FUNDING_RATE_PATH_URL, limit=9, time_interval=3),
    RateLimit(limit_id=GET_POSITIONS_PATH_URL, limit=9, time_interval=3),
    RateLimit(limit_id=QUERY_ORDER_BY_EXCHANGE_ORDER_ID_PATH_URL, limit=30, time_interval=3),
    RateLimit(limit_id=QUERY_ORDER_BY_CLIENT_ORDER_ID_PATH_URL, limit=30, time_interval=3),
    RateLimit(limit_id=QUERY_ACTIVE_ORDER_PATH_URL, limit=30, time_interval=3),
    RateLimit(limit_id=GET_WALLET_BALANCE_PATH_URL, limit=30, time_interval=3),
    RateLimit(limit_id=GET_CONTRACT_INFO_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=CREATE_ORDER_PATH_URL, limit=25, time_interval=3),
    RateLimit(limit_id=CANCEL_ORDER_PATH_URL, limit=35, time_interval=3),
    RateLimit(limit_id=GET_FILL_INFO_PATH_URL, limit=9, time_interval=3),
    RateLimit(limit_id=GET_RECENT_FILLS_INFO_PATH_URL, limit=9, time_interval=3),
    RateLimit(limit_id=GET_FUNDING_HISTORY_PATH_URL, limit=9, time_interval=3),
    RateLimit(limit_id=GET_RISK_LIMIT_LEVEL_PATH_URL, limit=9, time_interval=3),
]
