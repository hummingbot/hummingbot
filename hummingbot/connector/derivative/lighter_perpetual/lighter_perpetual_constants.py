from decimal import Decimal

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "lighter_perpetual"
DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "lighter_perpetual_testnet"

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
FUNDING_RATES_PATH_URL = "/api/v1/funding-rates"
POSITION_FUNDING_PATH_URL = "/api/v1/positionFunding"
EXCHANGE_STATS_PATH_URL = "/api/v1/exchangeStats"
CANDLES_PATH_URL = "/api/v1/candles"

DEFAULT_AUTH_TOKEN_EXPIRY_SECONDS = 10 * 60
AUTH_TOKEN_REFRESH_BUFFER_SECONDS = 30
FUNDING_INTERVAL_SECONDS = 60 * 60
DEFAULT_MARKET_ORDER_SLIPPAGE = Decimal("0.05")
DEFAULT_REQUEST_LIMIT = 250
MAX_CLIENT_ORDER_ID_BIT_COUNT = 48
ORDER_BOOK_SNAPSHOT_LIMIT = 250
PUBLIC_WS_PING_INTERVAL = 30.0
PRIVATE_WS_PING_INTERVAL = 30.0
MARKET_ID_ALL = 255
# Grace window after order creation during which a "not found" REST lookup is treated
# as "still pending" rather than an error — the on-chain tx may not be indexed yet.
ORDER_NOT_FOUND_GRACE_PERIOD = 10.0

ACCOUNT_LOOKUP_BY_INDEX = "index"
ACCOUNT_LOOKUP_BY_L1_ADDRESS = "l1_address"
ACCOUNT_LOOKUP_BY = ACCOUNT_LOOKUP_BY_INDEX
PERPETUAL_QUOTE_TOKEN = "USDC"
PERPETUAL_COLLATERAL_TOKEN = "USDC"

OPEN_ORDER_STATES = {"open", "pending", "in-progress"}
CANCELED_ORDER_STATES = {
    "canceled",
    "canceled-expired",
    "canceled-self-trade",
    "canceled-oco",
    "canceled-child",
    "canceled-liquidation",
    "canceled-reduce-only",
    "canceled-position-not-allowed",
}
FAILED_ORDER_STATES = {
    "canceled-post-only",
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
    "canceled-reduce-only": OrderState.CANCELED,
    "canceled-position-not-allowed": OrderState.CANCELED,
    "canceled-post-only": OrderState.FAILED,
    "canceled-margin-not-allowed": OrderState.FAILED,
    "canceled-too-much-slippage": OrderState.FAILED,
    "canceled-not-enough-liquidity": OrderState.FAILED,
    "canceled-invalid-balance": OrderState.FAILED,
}

ALL_ENDPOINTS_LIMIT = "lighter_perpetual_all"
SEND_TX_LIMIT = "lighter_perpetual_send_tx"

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
        FUNDING_RATES_PATH_URL,
        limit=DEFAULT_REQUEST_LIMIT,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        POSITION_FUNDING_PATH_URL,
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

COLLATERAL_TOKEN = PERPETUAL_COLLATERAL_TOKEN
QUOTE_TOKEN = PERPETUAL_QUOTE_TOKEN

TRADE_CHANNEL = "trade"
ORDER_BOOK_CHANNEL = "order_book"
MARKET_STATS_CHANNEL = "market_stats"
ACCOUNT_ALL_ORDERS_CHANNEL = "account_all_orders"
ACCOUNT_ALL_TRADES_CHANNEL = "account_all_trades"
ACCOUNT_ALL_ASSETS_CHANNEL = "account_all_assets"
ACCOUNT_ALL_POSITIONS_CHANNEL = "account_all_positions"

ORDER_NOT_EXIST_MESSAGE = "Order not found"
UNKNOWN_ORDER_MESSAGE = "Order not found"
