from hummingbot.connector.constants import SECOND
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "bithumb"
DEFAULT_PAYMENT_CURRENCY = "KRW"

REST_URL = "https://api.bithumb.com"
WS_URL = "wss://pubwss.bithumb.com/pub/ws"

MAX_ORDER_ID_LEN = 36
HBOT_ORDER_ID_PREFIX = "HBOT"

# Public REST endpoints
TICKER_ALL_PATH_URL = "/public/ticker/ALL_KRW"
TICKER_PATH_URL = "/public/ticker/{order_currency}_{payment_currency}"
ORDERBOOK_PATH_URL = "/public/orderbook/{order_currency}_{payment_currency}"
TRANSACTION_HISTORY_PATH_URL = "/public/transaction_history/{order_currency}_{payment_currency}"

# Private REST endpoints
BALANCE_PATH_URL = "/info/balance"
ORDER_DETAIL_PATH_URL = "/info/order_detail"
ORDERS_PATH_URL = "/info/orders"
USER_TRANSACTIONS_PATH_URL = "/info/user_transactions"
TRADE_PLACE_PATH_URL = "/trade/place"
TRADE_CANCEL_PATH_URL = "/trade/cancel"
TRADE_MARKET_BUY_PATH_URL = "/trade/market_buy"
TRADE_MARKET_SELL_PATH_URL = "/trade/market_sell"

# Rate limit IDs
PUBLIC_REST_LIMIT_ID = "bithumb_public_rest"
PRIVATE_REST_LIMIT_ID = "bithumb_private_rest"

# WebSocket event types
WS_ORDERBOOK_EVENT_TYPE = "orderbooksnapshot"
WS_TRADE_EVENT_TYPE = "transaction"

PING_INTERVAL = 30.0

ORDER_STATE = {
    "placed": OrderState.OPEN,
    "completed": OrderState.FILLED,
    "cancel": OrderState.CANCELED,
    "cancelled": OrderState.CANCELED,
}

RATE_LIMITS = [
    RateLimit(limit_id=PUBLIC_REST_LIMIT_ID, limit=10, time_interval=SECOND),
    RateLimit(limit_id=PRIVATE_REST_LIMIT_ID, limit=1, time_interval=SECOND),
    RateLimit(
        limit_id=TICKER_ALL_PATH_URL,
        limit=10,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=TICKER_PATH_URL,
        limit=10,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=ORDERBOOK_PATH_URL,
        limit=10,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=TRANSACTION_HISTORY_PATH_URL,
        limit=10,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=BALANCE_PATH_URL,
        limit=1,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=ORDER_DETAIL_PATH_URL,
        limit=1,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=ORDERS_PATH_URL,
        limit=1,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=USER_TRANSACTIONS_PATH_URL,
        limit=1,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=TRADE_PLACE_PATH_URL,
        limit=1,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=TRADE_CANCEL_PATH_URL,
        limit=1,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=TRADE_MARKET_BUY_PATH_URL,
        limit=1,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_REST_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=TRADE_MARKET_SELL_PATH_URL,
        limit=1,
        time_interval=SECOND,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_REST_LIMIT_ID)],
    ),
]
