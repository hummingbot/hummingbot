from enum import Enum

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionMode
from hummingbot.core.data_type.in_flight_order import OrderState


class MarginMode(Enum):
    CROSS = "CROSS"
    ISOLATED = "ISOLATED"


EXCHANGE_NAME = "bitget_perpetual"
DEFAULT_DOMAIN = EXCHANGE_NAME
REST_URLS = {DEFAULT_DOMAIN: "https://api.bitget.com"}
WSS_URLS = {DEFAULT_DOMAIN: "wss://ws.bitget.com"}
DEFAULT_TIME_IN_FORCE = "gtc"
# V3 UTA post-only (maker-only) timeInForce, used for LIMIT_MAKER orders.
POST_ONLY_TIME_IN_FORCE = "post_only"

# V3 UTA (Unified Trading Account). Futures are traded as the "<COIN>-FUTURES" categories of the
# unified account; the product-type constants below double as the V3 "category" request value.
# Private (account) websocket subscriptions use the "UTA" instType.
INST_TYPE_UTA = "UTA"

# V3 instruments listing state; only an online instrument accepts orders.
INSTRUMENT_STATUS_ONLINE = "online"

# Upper bound on cursor-paginated reads, so a cursor that never terminates cannot spin.
MAX_PAGINATION_PAGES = 20
# Rows requested per page; a shorter page means the last one.
PAGINATION_LIMIT = 100
# How far back the funding-payment lookup reads the financial records when no settlement turns up sooner.
FUNDING_PAYMENT_LOOKBACK_SECONDS = 24 * 60 * 60

ORDER_ID_MAX_LEN = None
HBOT_ORDER_ID_PREFIX = ""

WSS_PUBLIC_ENDPOINT = "/v3/ws/public"
WSS_PRIVATE_ENDPOINT = "/v3/ws/private"

MARGIN_MODE_TYPES = {
    MarginMode.CROSS: "crossed",
    MarginMode.ISOLATED: "isolated",
}
ORDER_TYPES = {
    OrderType.LIMIT: "limit",
    OrderType.LIMIT_MAKER: "limit",
    OrderType.MARKET: "market",
}
POSITION_MODE_TYPES = {
    PositionMode.ONEWAY: "one_way_mode",
    PositionMode.HEDGE: "hedge_mode",
}
STATE_TYPES = {
    "live": OrderState.OPEN,
    "new": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "partial_fill": OrderState.PARTIALLY_FILLED,
    "cancelled": OrderState.CANCELED,
    "canceled": OrderState.CANCELED,
}

SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 20
WS_HEARTBEAT_TIME_INTERVAL = 30

USDT_PRODUCT_TYPE = "USDT-FUTURES"
USDC_PRODUCT_TYPE = "USDC-FUTURES"
USD_PRODUCT_TYPE = "COIN-FUTURES"
ALL_PRODUCT_TYPES = [USDT_PRODUCT_TYPE, USDC_PRODUCT_TYPE, USD_PRODUCT_TYPE]

# Public (market data) V3 endpoints. The index/mark price that the V2 symbol-price endpoint used to
# return now comes from the unified tickers endpoint, so PUBLIC_SYMBOL_PRICE_ENDPOINT points there.
PUBLIC_TICKER_ENDPOINT = "/api/v3/market/tickers"
PUBLIC_CONTRACTS_ENDPOINT = "/api/v3/market/instruments"
PUBLIC_ORDERBOOK_ENDPOINT = "/api/v3/market/orderbook"
PUBLIC_FUNDING_RATE_ENDPOINT = "/api/v3/market/current-fund-rate"
PUBLIC_SYMBOL_PRICE_ENDPOINT = "/api/v3/market/tickers"
PUBLIC_TIME_ENDPOINT = "/api/v3/market/time"

# Private (account/trade/position) V3 endpoints
SET_LEVERAGE_ENDPOINT = "/api/v3/account/set-leverage"
ALL_POSITIONS_ENDPOINT = "/api/v3/position/current-position"
PLACE_ORDER_ENDPOINT = "/api/v3/trade/place-order"
CANCEL_ORDER_ENDPOINT = "/api/v3/trade/cancel-order"
ORDER_DETAIL_ENDPOINT = "/api/v3/trade/order-info"
ORDER_FILLS_ENDPOINT = "/api/v3/trade/fills"
ACCOUNTS_INFO_ENDPOINT = "/api/v3/account/assets"
USER_INFO_ENDPOINT = "/api/v3/account/info"
FEE_RATE_ENDPOINT = "/api/v3/account/fee-rate"
ACCOUNT_INFO_ENDPOINT = "/api/v3/account/settings"
SET_POSITION_MODE_ENDPOINT = "/api/v3/account/set-hold-mode"
SET_MARGIN_MODE_ENDPOINT = "/api/v3/account/adjust-account-mode"
ACCOUNT_BILLS_ENDPOINT = "/api/v3/account/financial-records"

# Classic (not upgraded to UTA) accounts trade through the V2 API. Market data comes from the V3 public
# endpoints above whatever the account mode; only these private calls, and the fee rates, differ.
CLASSIC_PUBLIC_CONTRACTS_ENDPOINT = "/api/v2/mix/market/contracts"
CLASSIC_SET_LEVERAGE_ENDPOINT = "/api/v2/mix/account/set-leverage"
CLASSIC_ALL_POSITIONS_ENDPOINT = "/api/v2/mix/position/all-position"
CLASSIC_PLACE_ORDER_ENDPOINT = "/api/v2/mix/order/place-order"
CLASSIC_CANCEL_ORDER_ENDPOINT = "/api/v2/mix/order/cancel-order"
CLASSIC_ORDER_DETAIL_ENDPOINT = "/api/v2/mix/order/detail"
CLASSIC_ORDER_FILLS_ENDPOINT = "/api/v2/mix/order/fills"
CLASSIC_ACCOUNTS_INFO_ENDPOINT = "/api/v2/mix/account/accounts"
CLASSIC_ACCOUNT_INFO_ENDPOINT = "/api/v2/mix/account/account"
CLASSIC_SET_POSITION_MODE_ENDPOINT = "/api/v2/mix/account/set-position-mode"
CLASSIC_SET_MARGIN_MODE_ENDPOINT = "/api/v2/mix/account/set-margin-mode"
CLASSIC_ACCOUNT_BILLS_ENDPOINT = "/api/v2/mix/account/bill"
CLASSIC_WSS_PRIVATE_ENDPOINT = "/v2/ws/private"
CLASSIC_WS_POSITIONS_ENDPOINT = "positions"
CLASSIC_WS_ORDERS_ENDPOINT = "orders"
CLASSIC_WS_ACCOUNT_ENDPOINT = "account"

API_CODE = "bntva"

PUBLIC_WS_BOOKS = "books"
PUBLIC_WS_TRADE = "publicTrade"
PUBLIC_WS_TICKER = "ticker"

PUBLIC_WS_PING_REQUEST = "ping"
PUBLIC_WS_PONG_RESPONSE = "pong"

# V3 UTA private websocket channels (singular under UTA)
WS_POSITIONS_ENDPOINT = "position"
WS_ORDERS_ENDPOINT = "order"
WS_ACCOUNT_ENDPOINT = "account"
WS_FILL_ENDPOINT = "fill"

RET_CODE_OK = "00000"
RET_CODE_PARAMS_ERROR = "40007"
RET_CODE_API_KEY_INVALID = "40006"
# Returned by the V3 UTA endpoints when the account has not been upgraded to the Unified Trading
# Account: "You are in Classic Account mode, and the Unified Account API is not supported at this time".
# This is how the connector tells a Classic account from a UTA one.
RET_CODE_CLASSIC_ACCOUNT = "40084"
# Pause between account mode reads while the user stream listener waits for the first one to succeed.
ACCOUNT_MODE_RETRY_INTERVAL_SECONDS = 5.0
# Pause before restarting the private websocket after Bitget rejects a subscription.
WS_SUBSCRIPTION_RETRY_INTERVAL_SECONDS = 10.0
RET_CODE_AUTH_TIMESTAMP_ERROR = "40005"

# No bare HTTP 404 here: Bitget answers an unknown path with 404/40404, which says nothing about the order
RET_CODES_ORDER_NOT_EXISTS = [
    "25204",
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
    RateLimit(limit_id=PUBLIC_SYMBOL_PRICE_ENDPOINT, limit=20, time_interval=1),

    RateLimit(limit_id=SET_LEVERAGE_ENDPOINT, limit=5, time_interval=1),
    RateLimit(limit_id=ALL_POSITIONS_ENDPOINT, limit=5, time_interval=1),
    RateLimit(limit_id=PLACE_ORDER_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=CANCEL_ORDER_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=ORDER_DETAIL_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=ORDER_FILLS_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=ACCOUNTS_INFO_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=USER_INFO_ENDPOINT, limit=1, time_interval=1),
    RateLimit(limit_id=FEE_RATE_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=ACCOUNT_INFO_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=ACCOUNT_BILLS_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=SET_POSITION_MODE_ENDPOINT, limit=5, time_interval=1),
    RateLimit(limit_id=SET_MARGIN_MODE_ENDPOINT, limit=5, time_interval=1),

    RateLimit(limit_id=CLASSIC_PUBLIC_CONTRACTS_ENDPOINT, limit=20, time_interval=1),
    RateLimit(limit_id=CLASSIC_SET_LEVERAGE_ENDPOINT, limit=5, time_interval=1),
    RateLimit(limit_id=CLASSIC_ALL_POSITIONS_ENDPOINT, limit=5, time_interval=1),
    RateLimit(limit_id=CLASSIC_PLACE_ORDER_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=CLASSIC_CANCEL_ORDER_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=CLASSIC_ORDER_DETAIL_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=CLASSIC_ORDER_FILLS_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=CLASSIC_ACCOUNTS_INFO_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=CLASSIC_ACCOUNT_INFO_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=CLASSIC_ACCOUNT_BILLS_ENDPOINT, limit=10, time_interval=1),
    RateLimit(limit_id=CLASSIC_SET_POSITION_MODE_ENDPOINT, limit=5, time_interval=1),
    RateLimit(limit_id=CLASSIC_SET_MARGIN_MODE_ENDPOINT, limit=5, time_interval=1),
]
