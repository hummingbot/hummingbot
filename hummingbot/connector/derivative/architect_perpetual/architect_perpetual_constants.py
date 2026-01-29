from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "architect_perpetual"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = 36

MARKET_ORDER_SLIPPAGE = 0.05

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "architect_perpetual_testnet"

PERPETUAL_ENDPOINT = "https://app.architect.co"
TESTNET_ENDPOINT = "https://sandbox.architect.co"

GRAPHQL_PORT = 443
GRPC_PORT = 443

FUNDING_RATE_UPDATE_INTERNAL_SECOND = 60

CURRENCY = "USD"

ORDER_STATE = {
    "open": OrderState.OPEN,
    "pending": OrderState.PENDING_CREATE,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "filled": OrderState.FILLED,
    "canceled": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
    "expired": OrderState.CANCELED,
}

HEARTBEAT_TIME_INTERVAL = 30.0

MAX_REQUEST = 1200
ALL_ENDPOINTS_LIMIT = "All"

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=MAX_REQUEST, time_interval=60),
    RateLimit(limit_id="place_order", limit=100, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id="cancel_order", limit=100, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id="get_account", limit=10, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id="get_positions", limit=10, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id="get_orders", limit=10, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id="get_fills", limit=10, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id="get_ticker", limit=20, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id="get_orderbook", limit=20, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id="list_symbols", limit=5, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
]

ORDER_NOT_EXIST_MESSAGE = "order not found"
UNKNOWN_ORDER_MESSAGE = "Order was never placed, already canceled, or filled"
