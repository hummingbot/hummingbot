from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "bit_com_perpetual"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = 32

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "bit_com_perpetual_testnet"

PERPETUAL_BASE_URL = "https://api.bit.com"

TESTNET_BASE_URL = "https://betaapi.bitexch.dev"

PERPETUAL_WS_URL = "wss://ws.bit.com"

TESTNET_WS_URL = "wss://betaws.bitexch.dev"

FUNDING_RATE_INTERNAL_MIL_SECOND = 10 * 1000

CURRENCY = "USD"

SNAPSHOT_REST_URL = "/linear/v1/orderbooks"

TICKER_PRICE_CHANGE_URL = "/linear/v1/tickers"

EXCHANGE_INFO_URL = "/linear/v1/instruments"

PING_URL = "/linear/v1/system/time"

GET_LAST_FUNDING_RATE_PATH_URL = "/linear/v1/funding_rate"

# Private API v1 Endpoints

CANCEL_ORDER_URL = "/linear/v1/cancel_orders"

ACCOUNT_TRADE_LIST_URL = "/linear/v1/user/trades"

ORDER_URL = "/linear/v1/orders"

CREATE_ORDER_URL = "/linear/v1/orders"

SET_LEVERAGE_URL = "/linear/v1/leverage_ratio"
USERSTREAM_AUTH_URL = "/v1/ws/auth"
USER_TRADES_ENDPOINT_NAME = "user_trade"
USER_ORDERS_ENDPOINT_NAME = "order"
USER_POSITIONS_ENDPOINT_NAME = "position"
USER_BALANCES_ENDPOINT_NAME = "um_account"
ORDERS_UPDATE_ENDPOINT_NAME = "depth"
TRADES_ENDPOINT_NAME = "trade"
FUNDING_INFO_STREAM_NAME = "ticker"

ACCOUNT_INFO_URL = "/um/v1/accounts"

POSITION_INFORMATION_URL = "/linear/v1/positions"

# Order Statuses

ORDER_STATE = {
    "pending": OrderState.OPEN,
    "open": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "cancelled": OrderState.CANCELED,
    "expired": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
}

PUBLIC_URL_POINTS_LIMIT_ID = "PublicPoints"
PRIVATE_TRADE_URL_POINTS_LIMIT_ID = "PrivateTradePoints"  # includes place-orders
PRIVATE_OTHER_URL_POINTS_LIMIT_ID = "PrivateOtherPoints"  # includes place-orders
UM_PUBLIC_URL_POINTS_LIMIT_ID = "UmPublicPoints"
UM_PRIVATE_URL_POINTS_LIMIT_ID = "UmPrivatePoints"  # includes place-orders

HEARTBEAT_TIME_INTERVAL = 30.0

MAX_REQUEST = 10

RATE_LIMITS = [
    # Pool Limits

    RateLimit(limit_id=PUBLIC_URL_POINTS_LIMIT_ID, limit=10, time_interval=1),
    RateLimit(limit_id=PRIVATE_TRADE_URL_POINTS_LIMIT_ID, limit=10, time_interval=1),
    RateLimit(limit_id=PRIVATE_OTHER_URL_POINTS_LIMIT_ID, limit=10, time_interval=1),
    RateLimit(limit_id=UM_PUBLIC_URL_POINTS_LIMIT_ID, limit=10, time_interval=1),
    RateLimit(limit_id=UM_PRIVATE_URL_POINTS_LIMIT_ID, limit=10, time_interval=1),

    # Weight Limits for individual endpoints
    RateLimit(limit_id=SNAPSHOT_REST_URL, limit=MAX_REQUEST, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=TICKER_PRICE_CHANGE_URL, limit=MAX_REQUEST, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=EXCHANGE_INFO_URL, limit=MAX_REQUEST, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=PING_URL, limit=MAX_REQUEST, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=ORDER_URL, limit=MAX_REQUEST, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_OTHER_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=CREATE_ORDER_URL, limit=MAX_REQUEST, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_TRADE_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=CANCEL_ORDER_URL, limit=MAX_REQUEST, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_TRADE_URL_POINTS_LIMIT_ID)]),

    RateLimit(limit_id=ACCOUNT_TRADE_LIST_URL, limit=MAX_REQUEST, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_OTHER_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=SET_LEVERAGE_URL, limit=MAX_REQUEST, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_OTHER_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=ACCOUNT_INFO_URL, limit=MAX_REQUEST, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(UM_PRIVATE_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=POSITION_INFORMATION_URL, limit=MAX_REQUEST, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_OTHER_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=GET_LAST_FUNDING_RATE_PATH_URL, limit=MAX_REQUEST, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=USERSTREAM_AUTH_URL, limit=MAX_REQUEST, time_interval=1),
]
