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
PERPETUAL_QUOTE_TOKEN = "USD"

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

# Rate limit constants
# https://apidocs.lighter.xyz/docs/rate-limits

# Endpoint weights (applied against the rolling-minute weighted bucket):
#   sendTx / sendTxBatch / nextNonce   →   6
#   accountInactiveOrders              →  100
#   trades / recentTrades              →  600
#   All other endpoints                →  300

# Standard account flat cap: 60 requests / rolling minute (unweighted).
# Premium account weighted cap: 24,000 weighted requests / rolling minute.
# Builder account weighted cap: 240,000 weighted requests / rolling minute.

# Endpoint weights (per single request)
WEIGHT_DEFAULT = 300          # "Other endpoints"
WEIGHT_SEND_TX = 6            # sendTx, sendTxBatch, nextNonce
WEIGHT_INACTIVE_ORDERS = 100  # accountInactiveOrders
WEIGHT_TRADES = 600           # trades, recentTrades

# Standard account flat cap (unweighted)
STANDARD_ACCOUNT_REQUEST_LIMIT = 60

# Total weighted-request pool for a standard account per rolling minute.
# Standard accounts are unweighted at 60 req/min; because the throttler uses
# a weight-based pool, we size the pool at 60 * WEIGHT_DEFAULT (=18 000) so
# that one "Other endpoint" call correctly costs 300 out of 18 000, giving
# the equivalent of 60 calls/min.  Upgrade tiers simply raise this ceiling.
ALL_ENDPOINTS_POOL = STANDARD_ACCOUNT_REQUEST_LIMIT * WEIGHT_DEFAULT  # 18 000

# Keep legacy alias
TRADES_RECENT_TRADES_LIMIT = WEIGHT_TRADES  # 600

# WebSocket limits (per IP) — https://apidocs.lighter.xyz/docs/rate-limits#websocket-limits
WS_MAX_CONNECTIONS = 200
WS_MAX_SUBSCRIPTIONS_PER_CONNECTION = 500
WS_MAX_UNIQUE_ACCOUNTS_PER_CONNECTION = 500
WS_MAX_NEW_CONNECTIONS_PER_MINUTE = 80
WS_MAX_MESSAGES_PER_MINUTE = 200   # sendTx/sendBatchTx excluded; follow REST limits
WS_MAX_INFLIGHT_MESSAGES = 50      # sendTx/sendBatchTx excluded

ALL_ENDPOINTS_LIMIT = "lighter_all"
SEND_TX_LIMIT = "lighter_send_tx"

RATE_LIMITS = [
    # ------------------------------------------------------------------
    # Shared pool — all REST requests draw from this bucket.
    # Sized for a standard account (60 unweighted req/min → 18 000 pts).
    # ------------------------------------------------------------------
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=ALL_ENDPOINTS_POOL, time_interval=60),

    # ------------------------------------------------------------------
    # sendTx / sendTxBatch — weight 6 per call.
    # Standard accounts: 60 req/min flat → pool of 360 (60 × 6).
    # ------------------------------------------------------------------
    RateLimit(
        SEND_TX_LIMIT,
        limit=STANDARD_ACCOUNT_REQUEST_LIMIT * WEIGHT_SEND_TX,  # 360
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_SEND_TX)],
    ),

    # ------------------------------------------------------------------
    # Read-only endpoints — "Other endpoints" weight = 300
    # ------------------------------------------------------------------
    RateLimit(
        ORDER_BOOK_DETAILS_PATH_URL,
        limit=WEIGHT_DEFAULT,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_DEFAULT)],
    ),
    RateLimit(
        ORDER_BOOK_ORDERS_PATH_URL,
        limit=WEIGHT_DEFAULT,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_DEFAULT)],
    ),
    RateLimit(
        ACCOUNT_PATH_URL,
        limit=WEIGHT_DEFAULT,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_DEFAULT)],
    ),
    RateLimit(
        ACCOUNT_ACTIVE_ORDERS_PATH_URL,
        limit=WEIGHT_DEFAULT,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_DEFAULT)],
    ),
    RateLimit(
        EXCHANGE_STATS_PATH_URL,
        limit=WEIGHT_DEFAULT,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_DEFAULT)],
    ),
    RateLimit(
        CANDLES_PATH_URL,
        limit=WEIGHT_DEFAULT,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_DEFAULT)],
    ),

    # ------------------------------------------------------------------
    # accountInactiveOrders — weight 100
    # ------------------------------------------------------------------
    RateLimit(
        ACCOUNT_INACTIVE_ORDERS_PATH_URL,
        limit=WEIGHT_INACTIVE_ORDERS,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_INACTIVE_ORDERS)],
    ),

    # ------------------------------------------------------------------
    # trades / recentTrades — weight 600
    # ------------------------------------------------------------------
    RateLimit(
        TRADES_PATH_URL,
        limit=WEIGHT_TRADES,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_TRADES)],
    ),
    RateLimit(
        RECENT_TRADES_PATH_URL,
        limit=WEIGHT_TRADES,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_TRADES)],
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
