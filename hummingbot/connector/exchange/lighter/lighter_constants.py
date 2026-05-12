from decimal import Decimal

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "lighter"
DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "lighter_testnet"

MAINNET_BASE_URL = "https://mainnet.zklighter.elliot.ai"
TESTNET_BASE_URL = "https://testnet.zklighter.elliot.ai"
MAINNET_WS_URL = "wss://mainnet.zklighter.elliot.ai/stream"
TESTNET_WS_URL = "wss://testnet.zklighter.elliot.ai/stream"

ORDER_BOOK_DETAILS_PATH_URL = "/api/v1/orderBookDetails"
ORDER_BOOK_ORDERS_PATH_URL = "/api/v1/orderBookOrders"
ACCOUNT_PATH_URL = "/api/v1/account"
ACCOUNT_ACTIVE_ORDERS_PATH_URL = "/api/v1/accountActiveOrders"
ACCOUNT_INACTIVE_ORDERS_PATH_URL = "/api/v1/accountInactiveOrders"
TRADES_PATH_URL = "/api/v1/trades"
RECENT_TRADES_PATH_URL = "/api/v1/recentTrades"
EXCHANGE_STATS_PATH_URL = "/api/v1/exchangeStats"
CANDLES_PATH_URL = "/api/v1/candles"

DEFAULT_AUTH_TOKEN_EXPIRY_SECONDS = 10 * 60
AUTH_TOKEN_REFRESH_BUFFER_SECONDS = 30
DEFAULT_MARKET_ORDER_SLIPPAGE = Decimal("0.05")
DEFAULT_REQUEST_LIMIT = 1000
MAX_CLIENT_ORDER_ID_BIT_COUNT = 48
ORDER_BOOK_SNAPSHOT_LIMIT = 250
PUBLIC_WS_PING_INTERVAL = 30.0
PRIVATE_WS_PING_INTERVAL = 30.0
MARKET_ID_ALL = 255

ACCOUNT_LOOKUP_BY_INDEX = "index"
ACCOUNT_LOOKUP_BY_L1_ADDRESS = "l1_address"
ACCOUNT_LOOKUP_BY = ACCOUNT_LOOKUP_BY_INDEX
PERPETUAL_QUOTE_TOKEN = "USD"

OPEN_ORDER_STATES = {"open", "pending", "in-progress"}
CANCELED_ORDER_STATES = {
    "canceled",
    "canceled-expired",
    "canceled-self-trade",
    "canceled-oco",
    "canceled-child",
    "canceled-liquidation",
}
FAILED_ORDER_STATES = {
    "canceled-post-only",
    "canceled-reduce-only",
    "canceled-position-not-allowed",
    "canceled-margin-not-allowed",
    "canceled-too-much-slippage",
    "canceled-not-enough-liquidity",
    "canceled-invalid-balance",
}

ORDER_STATE = {
    "open": OrderState.OPEN,
    "pending": OrderState.OPEN,
    "in-progress": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "canceled": OrderState.CANCELED,
    "canceled-expired": OrderState.CANCELED,
    "canceled-self-trade": OrderState.CANCELED,
    "canceled-oco": OrderState.CANCELED,
    "canceled-child": OrderState.CANCELED,
    "canceled-liquidation": OrderState.CANCELED,
    "canceled-post-only": OrderState.FAILED,
    "canceled-reduce-only": OrderState.FAILED,
    "canceled-position-not-allowed": OrderState.FAILED,
    "canceled-margin-not-allowed": OrderState.FAILED,
    "canceled-too-much-slippage": OrderState.FAILED,
    "canceled-not-enough-liquidity": OrderState.FAILED,
    "canceled-invalid-balance": OrderState.FAILED,
}

ALL_ENDPOINTS_LIMIT = "lighter_all"
SEND_TX_LIMIT = "lighter_send_tx"

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=DEFAULT_REQUEST_LIMIT, time_interval=60),
    RateLimit(SEND_TX_LIMIT, limit=DEFAULT_REQUEST_LIMIT, time_interval=60),
    RateLimit(
        ORDER_BOOK_DETAILS_PATH_URL,
        limit=DEFAULT_REQUEST_LIMIT,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        ORDER_BOOK_ORDERS_PATH_URL,
        limit=DEFAULT_REQUEST_LIMIT,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        ACCOUNT_PATH_URL,
        limit=DEFAULT_REQUEST_LIMIT,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        ACCOUNT_ACTIVE_ORDERS_PATH_URL,
        limit=DEFAULT_REQUEST_LIMIT,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        ACCOUNT_INACTIVE_ORDERS_PATH_URL,
        limit=DEFAULT_REQUEST_LIMIT,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        TRADES_PATH_URL,
        limit=DEFAULT_REQUEST_LIMIT,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        RECENT_TRADES_PATH_URL,
        limit=DEFAULT_REQUEST_LIMIT,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        EXCHANGE_STATS_PATH_URL,
        limit=DEFAULT_REQUEST_LIMIT,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        CANDLES_PATH_URL,
        limit=DEFAULT_REQUEST_LIMIT,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
]

BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = 19
MARKET_ORDER_SLIPPAGE = Decimal(str(DEFAULT_MARKET_ORDER_SLIPPAGE))

EXCHANGE_INFO_PATH_URL = ORDER_BOOK_DETAILS_PATH_URL
SNAPSHOT_PATH_URL = ORDER_BOOK_ORDERS_PATH_URL
BALANCE_PATH_URL = ACCOUNT_PATH_URL
PING_PATH_URL = EXCHANGE_STATS_PATH_URL

TRADE_CHANNEL = "trade"
ORDER_BOOK_CHANNEL = "order_book"
SPOT_MARKET_STATS_CHANNEL = "spot_market_stats"
ACCOUNT_ALL_ORDERS_CHANNEL = "account_all_orders"
ACCOUNT_ALL_TRADES_CHANNEL = "account_all_trades"
ACCOUNT_ALL_ASSETS_CHANNEL = "account_all_assets"

ORDER_NOT_EXIST_MESSAGE = "Order not found"
UNKNOWN_ORDER_MESSAGE = "Order not found"
