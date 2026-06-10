from decimal import Decimal
from typing import List

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
#   sendTx / sendTxBatch / nextNonce   →      6
#   accountInactiveOrders              →    100
#   trades / recentTrades              →    600
#   All other endpoints                →    300

# REST read-only pool caps (weighted requests / rolling minute):
#   Standard  →  60 unweighted req/min  (pool scaled to 60 × 300 = 18 000)
#   Premium   →  24,000
#   Plus      →  120,000
#   Builder   →  240,000
#
# sendTx / sendTxBatch caps (requests / rolling minute):
#   Standard  →  60 req/min  (shares the single Standard bucket; pool = 60 × 6 = 360)
#   Premium   →  4,000–40,000 depending on staked LIT (default baseline: 4,000)
#              INDEPENDENT of the read-only pool — getting tx-rate-limited does not
#              affect read-only calls and vice versa.
#   Plus      →  8,000  (independent of read-only pool)
#   Builder   →  60 req/min  (Standard rules apply for sendTx; independent of read-only pool)

# Endpoint weights (per single request)
WEIGHT_DEFAULT = 300  # "Other endpoints"
WEIGHT_SEND_TX = 6  # sendTx, sendTxBatch, nextNonce
WEIGHT_INACTIVE_ORDERS = 100  # accountInactiveOrders
WEIGHT_TRADES = 600  # trades, recentTrades

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

# sendTx / sendTxBatch caps per account tier (requests / rolling minute).
# Premium scales with staked LIT; the table below matches the docs exactly.
# https://apidocs.lighter.xyz/docs/rate-limits#sendtx-and-sendtxbatch-limits-premium-accounts
SEND_TX_LIMIT_STANDARD = STANDARD_ACCOUNT_REQUEST_LIMIT  # 60  — falls under single shared bucket
SEND_TX_LIMIT_PLUS = 8_000  # fixed, independent bucket
SEND_TX_LIMIT_BUILDER = STANDARD_ACCOUNT_REQUEST_LIMIT  # 60  — Standard rules apply for sendTx

# Premium sendTx limit by staked-LIT tier (use get_premium_send_tx_limit() below).
PREMIUM_SEND_TX_LIMITS_BY_STAKED_LIT = [
    (500_000, 40_000),
    (300_000, 24_000),
    (100_000, 12_000),
    (30_000, 8_000),
    (10_000, 7_000),
    (3_000, 6_000),
    (1_000, 5_000),
    (0, 4_000),  # baseline — no LIT staked
]


def get_premium_send_tx_limit(staked_lit: int = 0) -> int:
    """Return the correct sendTx/sendTxBatch cap (req/min) for a Premium account
    given the number of staked LIT tokens (fee credits count as staked LIT)."""
    for threshold, cap in PREMIUM_SEND_TX_LIMITS_BY_STAKED_LIT:
        if staked_lit >= threshold:
            return cap
    return 4_000  # unreachable, but safe fallback


# WebSocket limits (per IP) — https://apidocs.lighter.xyz/docs/rate-limits#websocket-limits
WS_MAX_CONNECTIONS = 200
WS_MAX_SUBSCRIPTIONS_PER_CONNECTION = 500
WS_MAX_UNIQUE_ACCOUNTS_PER_CONNECTION = 500
WS_MAX_NEW_CONNECTIONS_PER_MINUTE = 80
WS_MAX_MESSAGES_PER_MINUTE = 200  # sendTx/sendBatchTx excluded; follow REST limits
WS_MAX_INFLIGHT_MESSAGES = 50  # sendTx/sendBatchTx excluded

ALL_ENDPOINTS_LIMIT = "lighter_all"
SEND_TX_LIMIT = "lighter_send_tx"


def generate_account_limit(account_type: str, staked_lit: int = 0) -> List[RateLimit]:
    """Generate the full list of RateLimit objects for the given account tier.

    Parameters
    ----------
    account_type:
        One of "Standard", "Premium", "Plus", "Builder".
    staked_lit:
        Number of staked LIT tokens (only meaningful for Premium accounts).
        Fee credits count as staked LIT per the docs.
        Ignored for all other tiers.
    """
    # ------------------------------------------------------------------
    # Read-only (REST) pool sizes — weighted requests / rolling minute.
    # Standard is unweighted (60 req/min); we scale to 60 × WEIGHT_DEFAULT
    # so that one "Other endpoint" call correctly costs 300 out of 18 000,
    # giving the equivalent of 60 calls/min.
    # ------------------------------------------------------------------
    read_only_pool_map = {
        "Standard": STANDARD_ACCOUNT_REQUEST_LIMIT * WEIGHT_DEFAULT,  # 18,000
        "Premium": 24_000,
        "Plus": 120_000,
        "Builder": 240_000,
    }
    all_endpoints_pool = read_only_pool_map.get(account_type, STANDARD_ACCOUNT_REQUEST_LIMIT * WEIGHT_DEFAULT)

    # ------------------------------------------------------------------
    # sendTx / sendTxBatch pool sizes and linking rules.
    #
    # Standard : single shared bucket → sendTx IS linked to ALL_ENDPOINTS_LIMIT.
    #            Pool = 60 × WEIGHT_SEND_TX = 360 (60 unweighted calls × weight-6).
    #
    # Premium  : INDEPENDENT bucket, NOT linked to ALL_ENDPOINTS_LIMIT.
    #            Cap determined by staked LIT (4,000–40,000 req/min).
    #
    # Plus     : INDEPENDENT bucket, NOT linked to ALL_ENDPOINTS_LIMIT.
    #            Fixed cap of 8,000 req/min.
    #
    # Builder  : INDEPENDENT bucket, NOT linked to ALL_ENDPOINTS_LIMIT.
    #            Standard sendTx rules apply → 60 req/min.
    # ------------------------------------------------------------------
    if account_type == "Standard":
        send_tx_pool = SEND_TX_LIMIT_STANDARD * WEIGHT_SEND_TX  # 360
        send_tx_linked = [LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_SEND_TX)]
    elif account_type == "Premium":
        send_tx_pool = get_premium_send_tx_limit(staked_lit)  # 4,000–40,000
        send_tx_linked = []  # independent bucket
    elif account_type == "Plus":
        send_tx_pool = SEND_TX_LIMIT_PLUS  # 8,000
        send_tx_linked = []  # independent bucket
    else:  # Builder (and any unknown type — fall back to Standard sendTx rules)
        send_tx_pool = SEND_TX_LIMIT_BUILDER * WEIGHT_SEND_TX  # 360
        send_tx_linked = []  # independent bucket

    return [
        # ------------------------------------------------------------------
        # Shared read-only pool — all REST requests (except sendTx for
        # non-Standard tiers) draw from this bucket.
        # ------------------------------------------------------------------
        RateLimit(ALL_ENDPOINTS_LIMIT, limit=all_endpoints_pool, time_interval=60),
        # ------------------------------------------------------------------
        # sendTx / sendTxBatch bucket.
        # Standard: linked to ALL_ENDPOINTS_LIMIT (single shared pool).
        # All other tiers: standalone independent pool.
        # ------------------------------------------------------------------
        RateLimit(
            SEND_TX_LIMIT,
            limit=send_tx_pool,
            time_interval=60,
            linked_limits=send_tx_linked,
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
