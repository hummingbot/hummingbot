from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "evedex_perpetual"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = 36

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "evedex_perpetual_testnet"

PERPETUAL_BASE_URL = "https://api.evedex.com"
TESTNET_BASE_URL = "https://api-testnet.evedex.com"

PERPETUAL_WS_URL = "wss://ws.evedex.com/connection/websocket"
TESTNET_WS_URL = "wss://ws-testnet.evedex.com/connection/websocket"

AUTH_BASE_URL = "https://auth.evedex.com"
TESTNET_AUTH_BASE_URL = "https://auth-testnet.evedex.com"

CURRENCY = "USDT"
CHAIN_ID = 42161

TIME_IN_FORCE_GTC = "GTC"
TIME_IN_FORCE_IOC = "IOC"
TIME_IN_FORCE_FOK = "FOK"

EXCHANGE_INFO_URL = "/api/v1/public/markets"
TICKER_PRICE_URL = "/api/v1/public/ticker"
SNAPSHOT_REST_URL = "/api/v1/public/orderbook"
RECENT_TRADES_URL = "/api/v1/public/trades"
PING_URL = "/api/v1/public/time"
MARK_PRICE_URL = "/api/v1/public/funding"

ORDER_URL = "/api/v1/private/orders"
CANCEL_ORDER_URL = "/api/v1/private/orders/cancel"
CREATE_ORDER_URL = "/api/v1/private/orders"
ACCOUNT_INFO_URL = "/api/v1/private/account"
POSITION_INFORMATION_URL = "/api/v1/private/positions"
ACCOUNT_TRADE_LIST_URL = "/api/v1/private/trades"
SET_LEVERAGE_URL = "/api/v1/private/leverage"
GET_INCOME_HISTORY_URL = "/api/v1/private/funding"

ORDER_STATE = {
    "NEW": OrderState.OPEN,
    "OPEN": OrderState.OPEN,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "FILLED": OrderState.FILLED,
    "CANCELED": OrderState.CANCELED,
    "CANCELLED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.CANCELED,
}

HEARTBEAT_TIME_INTERVAL = 30.0
FUNDING_RATE_UPDATE_INTERVAL = 60

MAX_REQUEST = 30
ALL_ENDPOINTS_LIMIT = "All"
ONE_MINUTE = 60

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=MAX_REQUEST, time_interval=ONE_MINUTE),
    RateLimit(limit_id=SNAPSHOT_REST_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=TICKER_PRICE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=EXCHANGE_INFO_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=PING_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ORDER_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=CREATE_ORDER_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=CANCEL_ORDER_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ACCOUNT_TRADE_LIST_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=SET_LEVERAGE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ACCOUNT_INFO_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=POSITION_INFORMATION_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=GET_INCOME_HISTORY_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=MARK_PRICE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
]

ORDER_NOT_EXIST_MESSAGE = "Order not found"
UNKNOWN_ORDER_MESSAGE = "Unknown order"

WS_CHANNELS = {
    "orderbook": "orderbook",
    "trades": "trades",
    "ticker": "ticker",
    "orders": "orders",
    "positions": "positions",
    "balance": "balance",
}
