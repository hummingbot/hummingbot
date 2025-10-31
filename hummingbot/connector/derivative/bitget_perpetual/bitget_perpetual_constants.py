from enum import Enum

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionMode
from hummingbot.core.data_type.in_flight_order import OrderState


class MarginMode(Enum):
    CROSS = "CROSS"
    ISOLATED = "ISOLATED"


EXCHANGE_NAME = "bitget_perpetual"
DEFAULT_DOMAIN = "bitget.com"
REST_SUBDOMAIN = "api"
WSS_SUBDOMAIN = "ws"
DEFAULT_TIME_IN_FORCE = "gtc"

ORDER_ID_MAX_LEN = None
HBOT_ORDER_ID_PREFIX = ""

WSS_PUBLIC_ENDPOINT = "/v2/ws/public"
WSS_PRIVATE_ENDPOINT = "/v2/ws/private"

MARGIN_MODE_TYPES = {
    MarginMode.CROSS: "crossed",
    MarginMode.ISOLATED: "isolated",
}
ORDER_TYPES = {
    OrderType.LIMIT: "limit",
    OrderType.MARKET: "market",
}
POSITION_MODE_TYPES = {
    PositionMode.ONEWAY: "one_way_mode",
    PositionMode.HEDGE: "hedge_mode",
}
STATE_TYPES = {
    "live": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "cancelled": OrderState.CANCELED,
    "canceled": OrderState.CANCELED,
}

SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 20
WS_HEARTBEAT_TIME_INTERVAL = 30

USDT_PRODUCT_TYPE = "USDT-FUTURES"
USDC_PRODUCT_TYPE = "USDC-FUTURES"
USD_PRODUCT_TYPE = "COIN-FUTURES"
ALL_PRODUCT_TYPES = [USDT_PRODUCT_TYPE, USDC_PRODUCT_TYPE, USD_PRODUCT_TYPE]

PUBLIC_TICKER_ENDPOINT = "/api/v2/mix/market/ticker"
PUBLIC_CONTRACTS_ENDPOINT = "/api/v2/mix/market/contracts"
PUBLIC_ORDERBOOK_ENDPOINT = "/api/v2/mix/market/merge-depth"
PUBLIC_FUNDING_RATE_ENDPOINT = "/api/v2/mix/market/current-fund-rate"
PUBLIC_OPEN_INTEREST_ENDPOINT = "/api/v2/mix/market/open-interest"
PUBLIC_SYMBOL_PRICE_ENDPOINT = "/api/v2/mix/market/symbol-price"
PUBLIC_TIME_ENDPOINT = "/api/v2/public/time"
PUBLIC_FUNDING_TIME_ENDPOINT = "/api/v2/mix/market/funding-time"

SET_LEVERAGE_ENDPOINT = "/api/v2/mix/account/set-leverage"
ALL_POSITIONS_ENDPOINT = "/api/v2/mix/position/all-position"
PLACE_ORDER_ENDPOINT = "/api/v2/mix/order/place-order"
CANCEL_ORDER_ENDPOINT = "/api/v2/mix/order/cancel-order"
ORDER_DETAIL_ENDPOINT = "/api/v2/mix/order/detail"
ORDER_FILLS_ENDPOINT = "/api/v2/mix/order/fills"
ACCOUNTS_INFO_ENDPOINT = "/api/v2/mix/account/accounts"
ACCOUNT_INFO_ENDPOINT = "/api/v2/mix/account/account"
SET_POSITION_MODE_ENDPOINT = "/api/v2/mix/account/set-position-mode"
SET_MARGIN_MODE_ENDPOINT = "/api/v2/mix/account/set-margin-mode"
ACCOUNT_BILLS_ENDPOINT = "/api/v2/mix/account/bill"

API_CODE = "bntva"

PUBLIC_WS_BOOKS = "books"
PUBLIC_WS_TRADE = "trade"
PUBLIC_WS_TICKER = "ticker"

PUBLIC_WS_PING_REQUEST = "ping"
PUBLIC_WS_PONG_RESPONSE = "pong"

WS_POSITIONS_ENDPOINT = "positions"
WS_ORDERS_ENDPOINT = "orders"
WS_ACCOUNT_ENDPOINT = "account"

RET_CODE_OK = "00000"
RET_CODE_PARAMS_ERROR = "40007"
RET_CODE_API_KEY_INVALID = "40006"
RET_CODE_AUTH_TIMESTAMP_ERROR = "40005"
RET_CODES_ORDER_NOT_EXISTS = [
    "40768", "80011", "40819",
    "43020", "43025", "43001",
    "45057", "31007", "43033"
]
RET_CODE_API_KEY_EXPIRED = "40014"


RATE_LIMITS = [
    RateLimit(limit_id=PUBLIC_TICKER_ENDPOINT, limit=20, time_interval=1),
    RateLimit(limit_id=PUBLIC_CONTRACTS_ENDPOINT, limit=20, time_interval=1),
    RateLimit(limit_id=PUBLIC_ORDERBOOK_ENDPOINT, limit=20, time_interval=1),
    RateLimit(limit_id=PUBLIC_TIME_ENDPOINT, limit=20, time_interval=1),
    RateLimit(limit_id=PUBLIC_FUNDING_RATE_ENDPOINT, limit=20, time_interval=1),
    RateLimit(limit_id=PUBLIC_OPEN_INTEREST_ENDPOINT, limit=20, time_interval=1),
    RateLimit(limit_id=PUBLIC_SYMBOL_PRICE_ENDPOINT, limit=20, time_interval=1),
    RateLimit(limit_id=PUBLIC_FUNDING_TIME_ENDPOINT, limit=20, time_interval=1),

    RateLimit(limit_id=SET_LEVERAGE_ENDPOINT, limit=5, time_interval=1),
    RateLimit(limit_id=ALL_POSITIONS_ENDPOINT, limit=5, time_interval=1),
    RateLimit(limit_id=PLACE_ORDER_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=CANCEL_ORDER_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=ORDER_DETAIL_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=ORDER_FILLS_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=ACCOUNTS_INFO_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=ACCOUNT_INFO_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=ACCOUNT_BILLS_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=SET_POSITION_MODE_ENDPOINT, limit=5, time_interval=1),
    RateLimit(limit_id=SET_MARGIN_MODE_ENDPOINT, limit=5, time_interval=1),
]
