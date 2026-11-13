from hummingbot.connector.constants import SECOND
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = ""
REST_URL = "https://sapi.xt.com"
WSS_PUBLIC_URL = "wss://stream.xt.com/public"
WSS_PRIVATE_URL = "wss://stream.xt.com/private"

MAX_ORDER_ID_LEN = 22
HBOT_ORDER_ID_PREFIX = "HBOT"

XT_SUCCESS_CODE = 0
XT_SUCCESS_MESSAGE = "SUCCESS"

BIZ_TYPE_SPOT = "SPOT"
ORDER_TYPE_LIMIT = "LIMIT"
TIME_IN_FORCE_GTC = "GTC"
TIME_IN_FORCE_GTX = "GTX"
SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

ORDER_STATE = {
    "NEW": OrderState.OPEN,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "FILLED": OrderState.FILLED,
    "CANCELED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.CANCELED,
}

ORDER_NOT_FOUND_ERROR_CODE = "ORDER_005"
TIMESTAMP_ERROR_CODE = "AUTH_105"
TIMESTAMP_ERROR_MESSAGE = "Outdated message"

SERVER_TIME_PATH_URL = "/v4/public/time"
EXCHANGE_INFO_PATH_URL = "/v4/public/symbol"
DEPTH_PATH_URL = "/v4/public/depth"
RECENT_TRADES_PATH_URL = "/v4/public/trade/recent"
TICKER_PRICE_PATH_URL = "/v4/public/ticker/price"

ORDER_PATH_URL = "/v4/order"
ORDER_STATUS_PATH_URL = "/v4/order/{order_id}"
ORDER_HISTORY_PATH_URL = "/v4/history-order"
OPEN_ORDER_PATH_URL = "/v4/open-order"
TRADE_HISTORY_PATH_URL = "/v4/trade"
BALANCES_PATH_URL = "/v4/balances"
WS_TOKEN_PATH_URL = "/v4/ws-token"

WS_HEARTBEAT_TIME_INTERVAL = 5.0
WS_RESPONSE_TIMEOUT = 60.0
WS_SUBSCRIPTION_LIMIT_ID = "ws_subscription"
WS_PING_REQUEST = "ping"
WS_PONG_RESPONSE = "pong"

WS_PUBLIC_DEPTH_TOPIC = "depth_update"
WS_PUBLIC_TRADE_TOPIC = "trade"
WS_PRIVATE_ORDER_TOPIC = "order"
WS_PRIVATE_TRADE_TOPIC = "trade"
WS_PRIVATE_BALANCE_TOPIC = "balance"

RAW_REQUESTS_LIMIT_ID = "raw_requests"
REQUEST_WEIGHT_LIMIT_ID = "request_weight"
PRIVATE_ORDER_LIMIT_ID = "private_order"
PUBLIC_ORDER_BOOK_LIMIT_ID = "public_order_book"
PUBLIC_TICKER_LIMIT_ID = "public_ticker"
PUBLIC_TRADES_LIMIT_ID = "public_trades"

# A shared conservative budget stays below the documented per-endpoint limits.
# https://doc.xt.com/docs/spot/Access%20Description/FrequencyLimitingRules
MAX_REQUESTS_PER_SECOND = 8
MAX_WS_SUBSCRIPTIONS_PER_SECOND = 5

RATE_LIMITS = [
    RateLimit(limit_id=REQUEST_WEIGHT_LIMIT_ID, limit=MAX_REQUESTS_PER_SECOND, time_interval=SECOND),
    *[
        RateLimit(
            limit_id=limit_id,
            limit=MAX_REQUESTS_PER_SECOND,
            time_interval=SECOND,
            linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_LIMIT_ID)],
        )
        for limit_id in (
            SERVER_TIME_PATH_URL, EXCHANGE_INFO_PATH_URL, PUBLIC_ORDER_BOOK_LIMIT_ID,
            PUBLIC_TICKER_LIMIT_ID, PUBLIC_TRADES_LIMIT_ID, PRIVATE_ORDER_LIMIT_ID,
            ORDER_PATH_URL, ORDER_HISTORY_PATH_URL, OPEN_ORDER_PATH_URL,
            TRADE_HISTORY_PATH_URL, BALANCES_PATH_URL,
        )
    ],
    RateLimit(
        limit_id=WS_TOKEN_PATH_URL, limit=1, time_interval=10 * SECOND,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT_LIMIT_ID)],
    ),
    RateLimit(limit_id=WS_SUBSCRIPTION_LIMIT_ID, limit=MAX_WS_SUBSCRIPTIONS_PER_SECOND, time_interval=SECOND),
]
