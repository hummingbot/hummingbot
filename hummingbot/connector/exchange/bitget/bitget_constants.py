from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "bitget"
DEFAULT_DOMAIN = "bitget.com"
REST_SUBDOMAIN = "api"
WSS_SUBDOMAIN = "ws"
DEFAULT_TIME_IN_FORCE = "gtc"

ORDER_ID_MAX_LEN = None
HBOT_ORDER_ID_PREFIX = ""

WSS_PUBLIC_ENDPOINT = "/v2/ws/public"
WSS_PRIVATE_ENDPOINT = "/v2/ws/private"

TRADE_TYPES = {
    TradeType.BUY: "buy",
    TradeType.SELL: "sell",
}
ORDER_TYPES = {
    OrderType.LIMIT: "limit",
    OrderType.MARKET: "market",
}
STATE_TYPES = {
    "live": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "cancelled": OrderState.CANCELED,
}

SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 20
WS_HEARTBEAT_TIME_INTERVAL = 30

PUBLIC_ORDERBOOK_ENDPOINT = "/api/v2/spot/market/orderbook"
PUBLIC_SYMBOLS_ENDPOINT = "/api/v2/spot/public/symbols"
PUBLIC_TICKERS_ENDPOINT = "/api/v2/spot/market/tickers"
PUBLIC_TIME_ENDPOINT = "/api/v2/public/time"

ASSETS_ENDPOINT = "/api/v2/spot/account/assets"
CANCEL_ORDER_ENDPOINT = "/api/v2/spot/trade/cancel-order"
ORDER_INFO_ENDPOINT = "/api/v2/spot/trade/orderInfo"
PLACE_ORDER_ENDPOINT = "/api/v2/spot/trade/place-order"
USER_FILLS_ENDPOINT = "/api/v2/spot/trade/fills"

API_CODE = "bntva"

PUBLIC_WS_BOOKS = "books"
PUBLIC_WS_TRADE = "trade"

PUBLIC_WS_PING_REQUEST = "ping"
PUBLIC_WS_PONG_RESPONSE = "pong"

WS_ORDERS_ENDPOINT = "orders"
WS_ACCOUNT_ENDPOINT = "account"
WS_FILL_ENDPOINT = "fill"

RET_CODE_OK = "00000"
RET_CODE_CHANNEL_NOT_EXIST = "30001"
RET_CODE_ILLEGAL_REQUEST = "30002"
RET_CODE_INVALID_OP = "30003"
RET_CODE_USER_NEEDS_LOGIN = "30004"
RET_CODE_LOGIN_FAILED = "30005"
RET_CODE_REQUEST_TOO_MANY = "30006"
RET_CODE_REQUEST_OVER_LIMIT = "30007"
RET_CODE_ACCESS_KEY_INVALID = "30011"
RET_CODE_ACCESS_PASSPHRASE_INVALID = "30012"
RET_CODE_ACCESS_TIMESTAMP_INVALID = "30013"
RET_CODE_REQUEST_TIMESTAMP_EXPIRED = "30014"
RET_CODE_INVALID_SIGNATURE = "30015"
RET_CODE_PARAM_ERROR = "30016"

RET_CODES_ORDER_NOT_EXISTS = [
    "40768", "80011", "40819",
    "43020", "43025", "43001",
    "45057", "31007", "43033"
]

RATE_LIMITS = [
    RateLimit(limit_id=PUBLIC_ORDERBOOK_ENDPOINT, limit=20, time_interval=1),
    RateLimit(limit_id=PUBLIC_SYMBOLS_ENDPOINT, limit=20, time_interval=1),
    RateLimit(limit_id=PUBLIC_TICKERS_ENDPOINT, limit=20, time_interval=1),
    RateLimit(limit_id=PUBLIC_TIME_ENDPOINT, limit=10, time_interval=1),

    RateLimit(limit_id=ASSETS_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=CANCEL_ORDER_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=ORDER_INFO_ENDPOINT, limit=20, time_interval=1),
    RateLimit(limit_id=PLACE_ORDER_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=USER_FILLS_ENDPOINT, limit=10, time_interval=1),
]
