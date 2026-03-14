from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "grvt_perpetual"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = None
MIN_NOTIONAL_SIZE = 1.0

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "grvt_perpetual_testnet"

# GRVT has three endpoint types
MARKET_DATA_BASE_URL = "https://market-data.grvt.io"
TRADE_DATA_BASE_URL = "https://trades.grvt.io"
EDGE_BASE_URL = "https://edge.grvt.io"

TESTNET_MARKET_DATA_BASE_URL = "https://market-data.testnet.grvt.io"
TESTNET_TRADE_DATA_BASE_URL = "https://trades.testnet.grvt.io"
TESTNET_EDGE_BASE_URL = "https://edge.testnet.grvt.io"

MARKET_DATA_WS_URL = "wss://market-data.grvt.io/ws"
TRADE_DATA_WS_URL = "wss://trades.grvt.io/ws"

TESTNET_MARKET_DATA_WS_URL = "wss://market-data.testnet.grvt.io/ws"
TESTNET_TRADE_DATA_WS_URL = "wss://trades.testnet.grvt.io/ws"

# EIP-712 chain IDs
CHAIN_ID_PROD = 325
CHAIN_ID_TESTNET = 326

FUNDING_RATE_UPDATE_INTERNAL_SECOND = 60
CURRENCY = "USDT"
API_VERSION = "v1"

# REST endpoint paths (all use POST)
AUTH_URL = f"/auth/api_key/login"
INSTRUMENTS_URL = f"/full/{API_VERSION}/all_instruments"
TICKER_URL = f"/full/{API_VERSION}/ticker"
ORDERBOOK_URL = f"/full/{API_VERSION}/book"
ORDERBOOK_DEFAULT_DEPTH = 40  # must pass depth param explicitly
MINI_TICKER_URL = f"/full/{API_VERSION}/mini"
RECENT_TRADES_URL = f"/full/{API_VERSION}/trades"
FUNDING_RATE_URL = f"/full/{API_VERSION}/funding"

# Trade endpoints
CREATE_ORDER_URL = f"/full/{API_VERSION}/create_order"
CANCEL_ORDER_URL = f"/full/{API_VERSION}/cancel_order"
CANCEL_ALL_ORDERS_URL = f"/full/{API_VERSION}/cancel_all_orders"
GET_ORDER_URL = f"/full/{API_VERSION}/order"
GET_OPEN_ORDERS_URL = f"/full/{API_VERSION}/open_orders"
GET_ORDER_HISTORY_URL = f"/full/{API_VERSION}/order_history"
GET_FILL_HISTORY_URL = f"/full/{API_VERSION}/fill_history"
GET_POSITIONS_URL = f"/full/{API_VERSION}/positions"
GET_ACCOUNT_SUMMARY_URL = f"/full/{API_VERSION}/account_summary"

# WebSocket stream names
WS_TRADES_STREAM = "trades.v1"
WS_ORDERBOOK_STREAM = "book.v1"
WS_TICKER_STREAM = "ticker.v1"
WS_MINI_TICKER_STREAM = "mini.v1"
WS_ORDER_UPDATES_STREAM = "order.v1"
WS_POSITION_UPDATES_STREAM = "position.v1"
WS_FILL_UPDATES_STREAM = "fill.v1"

# Order states
ORDER_STATE = {
    "OPEN": OrderState.OPEN,
    "PENDING": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "CANCELLED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.CANCELED,
}

HEARTBEAT_TIME_INTERVAL = 30.0
MAX_REQUEST = 300
ALL_ENDPOINTS_LIMIT = "All"

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=MAX_REQUEST, time_interval=60),
    RateLimit(limit_id=INSTRUMENTS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=TICKER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=CREATE_ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=CANCEL_ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=GET_ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=GET_OPEN_ORDERS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=GET_POSITIONS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=GET_ACCOUNT_SUMMARY_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=GET_FILL_HISTORY_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=FUNDING_RATE_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
]

ORDER_NOT_EXIST_ERROR_CODE = "ECODE_INVALID_ORDER"
ORDER_NOT_EXIST_MESSAGE = "order not found"
UNKNOWN_ORDER_MESSAGE = "Order was never placed, already canceled, or filled"
