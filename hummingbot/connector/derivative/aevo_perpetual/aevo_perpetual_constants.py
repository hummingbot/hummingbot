from decimal import Decimal

from hummingbot.connector.constants import SECOND
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "aevo_perpetual"
BROKER_ID = "HBOT"

MAX_ORDER_ID_LEN = 32

PERPETUAL_INSTRUMENT_TYPE = "PERPETUAL"

MARKET_ORDER_SLIPPAGE = Decimal("0.01")

# REST endpoints
BASE_URL = "https://api.aevo.xyz"
TESTNET_BASE_URL = "https://api-testnet.aevo.xyz"

# WS endpoints
WSS_URL = "wss://ws.aevo.xyz"
TESTNET_WSS_URL = "wss://ws-testnet.aevo.xyz"

# Public REST API
PING_PATH_URL = "/time"
MARKETS_PATH_URL = "/markets"
ORDERBOOK_PATH_URL = "/orderbook"
FUNDING_PATH_URL = "/funding"
INSTRUMENT_PATH_URL = "/instrument"

# Private REST API
ACCOUNT_PATH_URL = "/account"
PORTFOLIO_PATH_URL = "/portfolio"
POSITIONS_PATH_URL = "/positions"
ORDERS_PATH_URL = "/orders"
ORDER_PATH_URL = "/orders/{order_id}"
ORDERS_ALL_PATH_URL = "/orders-all"
TRADE_HISTORY_PATH_URL = "/trade-history"
ACCOUNT_LEVERAGE_PATH_URL = "/account/leverage"
ACCOUNT_ACCUMULATED_FUNDINGS_PATH_URL = "/account/accumulated-fundings"

# WS channels
WS_ORDERBOOK_CHANNEL = "orderbook-100ms"
WS_TRADE_CHANNEL = "trades"
WS_TICKER_CHANNEL = "ticker-500ms"
WS_BOOK_TICKER_CHANNEL = "book-ticker"
WS_INDEX_CHANNEL = "index"

WS_ORDERS_CHANNEL = "orders"
WS_FILLS_CHANNEL = "fills"
WS_POSITIONS_CHANNEL = "positions"

WS_HEARTBEAT_TIME_INTERVAL = 30

NOT_EXIST_ERROR = "ORDER_DOES_NOT_EXIST"
REDUCE_ONLY_REJECTION_ERRORS = {
    "NO_POSITION_REDUCE_ONLY",
    "ORDER_EXCEEDS_CAPACITY_OF_REDUCE_ONLY",
    "INVALID_DIRECTION_REDUCE_ONLY",
}

# Order states
ORDER_STATE = {
    "opened": OrderState.OPEN,
    "partial": OrderState.PARTIALLY_FILLED,
    "filled": OrderState.FILLED,
    "cancelled": OrderState.CANCELED,
}

RATE_LIMITS = [
    RateLimit(limit_id=PING_PATH_URL, limit=10, time_interval=SECOND),
    RateLimit(limit_id=MARKETS_PATH_URL, limit=10, time_interval=SECOND),
    RateLimit(limit_id=ORDERBOOK_PATH_URL, limit=10, time_interval=SECOND),
    RateLimit(limit_id=FUNDING_PATH_URL, limit=10, time_interval=SECOND),
    RateLimit(limit_id=INSTRUMENT_PATH_URL, limit=10, time_interval=SECOND),
    RateLimit(limit_id=ACCOUNT_PATH_URL, limit=10, time_interval=SECOND),
    RateLimit(limit_id=PORTFOLIO_PATH_URL, limit=10, time_interval=SECOND),
    RateLimit(limit_id=POSITIONS_PATH_URL, limit=10, time_interval=SECOND),
    RateLimit(limit_id=ORDERS_PATH_URL, limit=10, time_interval=SECOND),
    RateLimit(limit_id=ORDERS_ALL_PATH_URL, limit=10, time_interval=SECOND),
    RateLimit(limit_id=TRADE_HISTORY_PATH_URL, limit=10, time_interval=SECOND),
    RateLimit(limit_id=ACCOUNT_LEVERAGE_PATH_URL, limit=10, time_interval=SECOND),
    RateLimit(limit_id=ACCOUNT_ACCUMULATED_FUNDINGS_PATH_URL, limit=10, time_interval=SECOND),
    RateLimit(limit_id=WSS_URL, limit=10, time_interval=SECOND),
    RateLimit(limit_id=TESTNET_WSS_URL, limit=10, time_interval=SECOND),
]
