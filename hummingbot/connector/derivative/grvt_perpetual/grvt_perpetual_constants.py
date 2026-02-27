from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "grvt_perpetual"
BROKER_ID = "HBOT"

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "grvt_perpetual_testnet"

# REST base URLs
PERPETUAL_BASE_EDGE_URL = "https://edge.grvt.io"
PERPETUAL_BASE_TRADE_URL = "https://trades.grvt.io"
PERPETUAL_BASE_MARKET_URL = "https://market-data.grvt.io"

TESTNET_BASE_EDGE_URL = "https://edge.testnet.grvt.io"
TESTNET_BASE_TRADE_URL = "https://trades.testnet.grvt.io"
TESTNET_BASE_MARKET_URL = "https://market-data.testnet.grvt.io"

# WebSocket URLs
PERPETUAL_WS_MARKET_URL = "wss://market-data.grvt.io/ws"
PERPETUAL_WS_TRADE_URL = "wss://trades.grvt.io/ws"

TESTNET_WS_MARKET_URL = "wss://market-data.testnet.grvt.io/ws"
TESTNET_WS_TRADE_URL = "wss://trades.testnet.grvt.io/ws"

# REST endpoint paths
AUTH_PATH = "auth/api_key/login"
CREATE_ORDER_PATH = "full/v1/create_order"
CANCEL_ORDER_PATH = "full/v1/cancel_order"
CANCEL_ALL_ORDERS_PATH = "full/v1/cancel_all_orders"
GET_OPEN_ORDERS_PATH = "full/v1/open_orders"
GET_ORDER_PATH = "full/v1/order"
GET_ORDER_HISTORY_PATH = "full/v1/order_history"
GET_POSITIONS_PATH = "full/v1/positions"
GET_ACCOUNT_SUMMARY_PATH = "full/v1/account_summary"
GET_FILL_HISTORY_PATH = "full/v1/fill_history"
GET_ALL_INSTRUMENTS_PATH = "full/v1/all_instruments"
GET_INSTRUMENTS_PATH = "full/v1/instruments"
GET_TICKER_PATH = "full/v1/ticker"
GET_MINI_TICKER_PATH = "full/v1/mini"
GET_ORDER_BOOK_PATH = "full/v1/book"
GET_TRADES_PATH = "full/v1/trade"
GET_CANDLESTICK_PATH = "full/v1/kline"
GET_FUNDING_PATH = "full/v1/funding"

# WebSocket stream names
WS_BOOK_SNAPSHOT = "book.s"
WS_BOOK_DELTA = "book.d"
WS_TRADE = "trade"
WS_CANDLE = "candle"
WS_ORDER = "order"
WS_FILL = "fill"
WS_POSITION = "position"

# EIP-712
CHAIN_ID_PROD = 325
CHAIN_ID_TESTNET = 326
EIP712_DOMAIN_NAME = "GRVT Exchange"
EIP712_DOMAIN_VERSION = "0"
PRICE_MULTIPLIER = 1_000_000_000

FUNDING_RATE_UPDATE_INTERVAL_SECOND = 3600

CURRENCY = "USDT"

# Order states mapping
ORDER_STATE = {
    "OPEN": OrderState.OPEN,
    "PENDING": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "CANCELLED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.CANCELED,
}

# Rate limits — GRVT doesn't publish explicit limits; use conservative defaults
RATE_LIMIT_ID = "grvt_perpetual"
NO_LIMIT = "NO_LIMIT"

RATE_LIMITS = [
    RateLimit(limit_id=NO_LIMIT, limit=500, time_interval=60),
    RateLimit(limit_id=CREATE_ORDER_PATH, limit=100, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(NO_LIMIT, 1)]),
    RateLimit(limit_id=CANCEL_ORDER_PATH, limit=100, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(NO_LIMIT, 1)]),
    RateLimit(limit_id=GET_OPEN_ORDERS_PATH, limit=100, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(NO_LIMIT, 1)]),
    RateLimit(limit_id=GET_POSITIONS_PATH, limit=100, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(NO_LIMIT, 1)]),
    RateLimit(limit_id=GET_ACCOUNT_SUMMARY_PATH, limit=100, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(NO_LIMIT, 1)]),
    RateLimit(limit_id=GET_ALL_INSTRUMENTS_PATH, limit=100, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(NO_LIMIT, 1)]),
    RateLimit(limit_id=GET_ORDER_BOOK_PATH, limit=100, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(NO_LIMIT, 1)]),
    RateLimit(limit_id=GET_TICKER_PATH, limit=100, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(NO_LIMIT, 1)]),
    RateLimit(limit_id=GET_FUNDING_PATH, limit=100, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(NO_LIMIT, 1)]),
    RateLimit(limit_id=GET_FILL_HISTORY_PATH, limit=100, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(NO_LIMIT, 1)]),
]
