from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "grvt_perpetual"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = 64

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "grvt_perpetual_testnet"

# ---- REST Base URLs ----
PERPETUAL_BASE_URL = "https://trades.grvt.io/full/v1/"
TESTNET_BASE_URL = "https://trades.testnet.grvt.io/full/v1/"

# ---- Market Data Base URLs ----
MARKET_DATA_BASE_URL = "https://market-data.grvt.io/full/v1/"
TESTNET_MARKET_DATA_BASE_URL = "https://market-data.testnet.grvt.io/full/v1/"

# ---- Auth Base URLs ----
AUTH_BASE_URL = "https://edge.grvt.io/auth/api_key/login"
TESTNET_AUTH_BASE_URL = "https://edge.testnet.grvt.io/auth/api_key/login"

# ---- WebSocket URLs ----
PERPETUAL_WS_URL = "wss://market-data.grvt.io/ws/full"
TESTNET_WS_URL = "wss://market-data.testnet.grvt.io/ws/full"

PERPETUAL_TRADE_WS_URL = "wss://trades.grvt.io/ws/full"
TESTNET_TRADE_WS_URL = "wss://trades.testnet.grvt.io/ws/full"

# ---- Time in Force ----
TIME_IN_FORCE_GTC = "GOOD_TILL_TIME"
TIME_IN_FORCE_IOC = "IMMEDIATE_OR_CANCEL"
TIME_IN_FORCE_FOK = "FILL_OR_KILL"

# ---- Public API Endpoints (Market Data) ----
ALL_INSTRUMENTS_URL = "all_instruments"
GET_INSTRUMENT_URL = "instrument"
FILTERED_INSTRUMENTS_URL = "instruments"
ORDERBOOK_URL = "book"
TICKER_URL = "ticker"
MINI_TICKER_URL = "mini"
TRADE_URL = "trade"
TRADE_HISTORY_URL = "trade_history"
KLINE_URL = "kline"
FUNDING_RATE_URL = "funding"

# ---- Private API Endpoints (Trading) ----
CREATE_ORDER_URL = "create_order"
CANCEL_ORDER_URL = "cancel_order"
CANCEL_ALL_ORDERS_URL = "cancel_all_orders"
GET_ORDER_URL = "order"
OPEN_ORDERS_URL = "open_orders"
ORDER_HISTORY_URL = "order_history"

# ---- Execution Endpoints ----
FILL_HISTORY_URL = "fill_history"
FUNDING_PAYMENT_HISTORY_URL = "funding_payment_history"

# ---- Position Endpoints ----
POSITIONS_URL = "positions"
SET_POSITION_CONFIG_URL = "set_position_config"
ADD_POSITION_MARGIN_URL = "add_position_margin"

# ---- Account Endpoints ----
ACCOUNT_SUMMARY_URL = "account_summary"
AGGREGATED_ACCOUNT_SUMMARY_URL = "aggregated_account_summary"
GET_SUB_ACCOUNTS_URL = "get_sub_accounts"

# ---- Leverage Endpoints ----
SET_INITIAL_LEVERAGE_URL = "set_initial_leverage"
GET_ALL_INITIAL_LEVERAGE_URL = "get_all_initial_leverage"

# ---- WS Stream Names ----
WS_ORDER_BOOK_SNAP_STREAM = "v1.book.s"
WS_ORDER_BOOK_DELTA_STREAM = "v1.book.d"
WS_TRADE_STREAM = "v1.trade"
WS_MINI_TICKER_SNAP_STREAM = "v1.mini.s"
WS_TICKER_SNAP_STREAM = "v1.ticker.s"
WS_CANDLE_STREAM = "v1.candle"

# ---- Private WS Stream Names ----
WS_ORDER_STREAM = "v1.order"
WS_ORDER_STATE_STREAM = "v1.state"
WS_FILL_STREAM = "v1.fill"
WS_POSITION_STREAM = "v1.position"

# ---- Funding Settlement Time Span ----
FUNDING_SETTLEMENT_DURATION = (0, 30)  # seconds before snapshot, seconds after snapshot

# ---- Order States ----
ORDER_STATE = {
    "PENDING": OrderState.PENDING_CREATE,
    "OPEN": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "CANCELLED": OrderState.CANCELED,
    "CANCELED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.CANCELED,
}

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS_LIMIT = "ORDERS_LIMIT"

DIFF_STREAM_ID = 1
TRADE_STREAM_ID = 2
FUNDING_INFO_STREAM_ID = 3
HEARTBEAT_TIME_INTERVAL = 30.0

# Rate Limit time intervals
ONE_HOUR = 3600
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 1200

RATE_LIMITS = [
    # Pool Limits
    RateLimit(limit_id=REQUEST_WEIGHT, limit=1200, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS_LIMIT, limit=300, time_interval=ONE_MINUTE),
    # Weight Limits for individual endpoints
    RateLimit(limit_id=ALL_INSTRUMENTS_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=10)]),
    RateLimit(limit_id=GET_INSTRUMENT_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=FILTERED_INSTRUMENTS_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=ORDERBOOK_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=TICKER_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=MINI_TICKER_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=TRADE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=FUNDING_RATE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=CREATE_ORDER_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1),
                             LinkedLimitWeightPair(ORDERS_LIMIT, weight=1)]),
    RateLimit(limit_id=CANCEL_ORDER_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=CANCEL_ALL_ORDERS_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=GET_ORDER_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=OPEN_ORDERS_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=ORDER_HISTORY_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=FILL_HISTORY_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=FUNDING_PAYMENT_HISTORY_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=POSITIONS_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=SET_INITIAL_LEVERAGE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=GET_ALL_INITIAL_LEVERAGE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=ACCOUNT_SUMMARY_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=AGGREGATED_ACCOUNT_SUMMARY_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
]

ORDER_NOT_EXIST_ERROR_CODE = 1002
ORDER_NOT_EXIST_MESSAGE = "Order does not exist"
UNKNOWN_ORDER_ERROR_CODE = 1003
UNKNOWN_ORDER_MESSAGE = "Unknown order sent"
