from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "grvt_perpetual"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = 32

MARKET_ORDER_SLIPPAGE = 0.05

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "grvt_perpetual_testnet"

# ---------- Base URLs (triple-host architecture) ----------

# Edge (Auth)
EDGE_BASE_URL = "https://edge.grvt.io"
TESTNET_EDGE_BASE_URL = "https://edge.testnet.grvt.io"

# Trade Data (authenticated endpoints)
TRADE_BASE_URL = "https://trades.grvt.io"
TESTNET_TRADE_BASE_URL = "https://trades.testnet.grvt.io"

# Market Data (public endpoints)
MARKET_DATA_BASE_URL = "https://market-data.grvt.io"
TESTNET_MARKET_DATA_BASE_URL = "https://market-data.testnet.grvt.io"

# ---------- WebSocket URLs ----------

MARKET_WS_URL = "wss://market-data.grvt.io/ws"
TESTNET_MARKET_WS_URL = "wss://market-data.testnet.grvt.io/ws"

MARKET_WS_FULL_URL = "wss://market-data.grvt.io/ws/full"
TESTNET_MARKET_WS_FULL_URL = "wss://market-data.testnet.grvt.io/ws/full"

TRADE_WS_URL = "wss://trades.grvt.io/ws"
TESTNET_TRADE_WS_URL = "wss://trades.testnet.grvt.io/ws"

TRADE_WS_FULL_URL = "wss://trades.grvt.io/ws/full"
TESTNET_TRADE_WS_FULL_URL = "wss://trades.testnet.grvt.io/ws/full"

# ---------- EIP-712 Chain IDs ----------

MAINNET_CHAIN_ID = 325
TESTNET_CHAIN_ID = 326

# ---------- Precision ----------

PRICE_PRECISION = 10 ** 9  # multiply by 1e9 for signing

# ---------- Funding ----------

FUNDING_RATE_UPDATE_INTERNAL_SECOND = 60

# ---------- Currency ----------

CURRENCY = "USDT"

# ---------- Auth Endpoints (Edge host, POST) ----------

AUTH_LOGIN_URL = "/auth/api_key/login"

# ---------- Market Data Endpoints (Market Data host, POST) ----------

ALL_INSTRUMENTS_URL = "/full/v1/all_instruments"
ORDERBOOK_URL = "/full/v1/book"
TICKER_URL = "/full/v1/ticker"
RECENT_TRADES_URL = "/full/v1/trade"
FUNDING_RATE_URL = "/full/v1/funding"

# ---------- Trade Data Endpoints (Trade host, POST, authenticated) ----------

CREATE_ORDER_URL = "/full/v1/create_order"
CANCEL_ORDER_URL = "/full/v1/cancel_order"
CANCEL_ALL_ORDERS_URL = "/full/v1/cancel_all_orders"
OPEN_ORDERS_URL = "/full/v1/open_orders"
ORDER_URL = "/full/v1/order"
FILL_HISTORY_URL = "/full/v1/fill_history"
POSITIONS_URL = "/full/v1/positions"
ACCOUNT_SUMMARY_URL = "/full/v1/account_summary"
FUNDING_PAYMENT_HISTORY_URL = "/full/v1/funding_payment_history"

# ---------- Aliases for framework compatibility ----------

TICKER_PRICE_CHANGE_URL = TICKER_URL
SNAPSHOT_REST_URL = ORDERBOOK_URL
EXCHANGE_INFO_URL = ALL_INSTRUMENTS_URL
ACCOUNT_TRADE_LIST_URL = FILL_HISTORY_URL
ACCOUNT_INFO_URL = ACCOUNT_SUMMARY_URL
POSITION_INFORMATION_URL = POSITIONS_URL
SET_LEVERAGE_URL = CREATE_ORDER_URL  # GRVT leverage is set per-order, no separate endpoint
GET_LAST_FUNDING_RATE_PATH_URL = FUNDING_PAYMENT_HISTORY_URL
PING_URL = ALL_INSTRUMENTS_URL  # Use instruments endpoint as health check

# ---------- WS Stream Names ----------

WS_TRADES_CHANNEL = "trade"
WS_BOOK_CHANNEL = "book.s"
WS_BOOK_FULL_CHANNEL = "book.d"
WS_TICKER_CHANNEL = "ticker.s"
WS_TICKER_FULL_CHANNEL = "ticker.d"
WS_MINI_CHANNEL = "mini.s"
WS_CANDLE_CHANNEL = "candle"

# Private WS streams (trade host)
WS_ORDER_CHANNEL = "order"
WS_ORDER_STATE_CHANNEL = "state"
WS_CANCEL_CHANNEL = "cancel"
WS_POSITION_CHANNEL = "position"
WS_FILL_CHANNEL = "fill"

# ---------- Order Status Mapping ----------

ORDER_STATE = {
    "PENDING": OrderState.PENDING_CREATE,
    "OPEN": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "REJECTED": OrderState.FAILED,
    "CANCELLED": OrderState.CANCELED,
}

# ---------- Heartbeat ----------

HEARTBEAT_TIME_INTERVAL = 30.0

# ---------- Rate Limits ----------

MAX_REQUEST = 1_200
ALL_ENDPOINTS_LIMIT = "All"

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=MAX_REQUEST, time_interval=60),

    # Market Data endpoints
    RateLimit(limit_id=ALL_INSTRUMENTS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ORDERBOOK_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=TICKER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=RECENT_TRADES_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=FUNDING_RATE_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),

    # Trade Data endpoints
    RateLimit(limit_id=CREATE_ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=CANCEL_ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=CANCEL_ALL_ORDERS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=OPEN_ORDERS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=FILL_HISTORY_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=POSITIONS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ACCOUNT_SUMMARY_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=FUNDING_PAYMENT_HISTORY_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),

    # Auth endpoints
    RateLimit(limit_id=AUTH_LOGIN_URL, limit=10, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
]

ORDER_NOT_EXIST_MESSAGE = "order not found"
UNKNOWN_ORDER_MESSAGE = "Order was never placed, already canceled, or filled"

# ---------- Instrument format ----------
# GRVT uses: BTC_USDT_Perp, ETH_USDT_Perp, etc.
INSTRUMENT_SUFFIX = "_Perp"
