from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

# ---------------------------------------------------------------------------
# Domain + base URL
# ---------------------------------------------------------------------------

DEFAULT_DOMAIN = "com"

# The connector is pre-WebSocket; only REST is used today.
REST_URL = "https://{}-api.kalqix.com/v1"
REST_URL_DOMAINS = {
    "com": "",            # production: https://api.kalqix.com/v1
    "testnet": "testnet",  # https://testnet-api.kalqix.com/v1
}


def rest_url(domain: str = DEFAULT_DOMAIN) -> str:
    prefix = REST_URL_DOMAINS.get(domain, "")
    if prefix == "":
        return "https://api.kalqix.com/v1"
    return f"https://{prefix}-api.kalqix.com/v1"


# Hummingbot's connector framework asks for these in some places even though
# the connector is REST-only today. Set to None so any accidental use raises.
WSS_URL: str = None

# ---------------------------------------------------------------------------
# Client order ID
# ---------------------------------------------------------------------------

# Prefix carries the partner tag for tracking; KalqiX does not enforce it,
# but Hummingbot uses the prefix convention across all connectors.
HBOT_ORDER_ID_PREFIX = "x-HBOT-KALQIX"
MAX_ORDER_ID_LEN = 64  # mirrors `client_order_id` regex `^[A-Za-z0-9_-]{1,64}$`

# ---------------------------------------------------------------------------
# Public REST paths
# ---------------------------------------------------------------------------

SERVER_TIME_PATH_URL = "/time"
PING_PATH_URL = "/ping"
EXCHANGE_INFO_PATH_URL = "/markets"
MARKET_PATH_URL = "/markets/{ticker}"          # underscore-form ticker in URL
MARKET_PRICE_PATH_URL = "/markets/{ticker}/price"
SNAPSHOT_PATH_URL = "/markets/{ticker}/order-book"
TRADES_PATH_URL = "/markets/{ticker}/trades"

# ---------------------------------------------------------------------------
# Private REST paths
# ---------------------------------------------------------------------------

ORDERS_PATH_URL = "/orders"
ORDER_BY_ID_PATH_URL = "/orders/{id}"
ORDER_TRADES_PATH_URL = "/orders/{id}/trades"
POSITIONS_PATH_URL = "/positions"
USER_TRADES_PATH_URL = "/users/me/trades"
CANCEL_ALL_PATH_URL = "/users/me/cancel-all-orders"

# ---------------------------------------------------------------------------
# Order params
# ---------------------------------------------------------------------------

SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

ORDER_TYPE_LIMIT = "LIMIT"
ORDER_TYPE_MARKET = "MARKET"

# KalqiX uses integer time-in-force values, not strings.
TIME_IN_FORCE_GTC = 0
TIME_IN_FORCE_IOC = 1
TIME_IN_FORCE_FOK = 2

# ---------------------------------------------------------------------------
# Order-state mapping  (KalqiX status → Hummingbot OrderState)
# ---------------------------------------------------------------------------

# KalqiX `PENDING` is an order resting on the book
# (pre-engine-ack or otherwise idle), so it maps to Hummingbot's `OPEN`. The
# `PENDING_CREATE` slot is for the local "we POSTed but haven't seen a server
# response" gap that the framework manages itself — we should never overwrite
# it from server-side state.
ORDER_STATE = {
    "PENDING": OrderState.OPEN,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "FILLED": OrderState.FILLED,
    "CANCELLATION_REQUESTED": OrderState.OPEN,   # still cancellable in the engine
    "CANCELLED": OrderState.CANCELED,
    "EXPIRED": OrderState.CANCELED,
    "EXPIRED_IN_MATCH": OrderState.CANCELED,
    "FAILED": OrderState.FAILED,
}

# ---------------------------------------------------------------------------
# Rate limits
# ---------------------------------------------------------------------------
#
# Server enforces two buckets:
#   - IP bucket:     1,000 req/s/IP   (open + closed routes)
#   - Wallet bucket: 18,000 req/min/wallet (closed routes only)
#
# The wallet bucket is the binding one for an authenticated bot.
# Express both here so the throttler smooths to whichever fires first.

ONE_SECOND = 1
ONE_MINUTE = 60

IP_REQUEST_POOL = "IP_REQUEST_POOL"
WALLET_REQUEST_POOL = "WALLET_REQUEST_POOL"

# Every request consumes 1 from each pool. No per-endpoint weighting on the
# server today, so use uniform weight.
RATE_LIMITS = [
    # Pools
    RateLimit(limit_id=IP_REQUEST_POOL, limit=1000, time_interval=ONE_SECOND),
    RateLimit(limit_id=WALLET_REQUEST_POOL, limit=18000, time_interval=ONE_MINUTE),

    # Endpoints
    *[
        RateLimit(
            limit_id=path,
            limit=18000,
            time_interval=ONE_MINUTE,
            linked_limits=[
                LinkedLimitWeightPair(IP_REQUEST_POOL, 1),
                LinkedLimitWeightPair(WALLET_REQUEST_POOL, 1),
            ],
        )
        for path in [
            SERVER_TIME_PATH_URL,
            PING_PATH_URL,
            EXCHANGE_INFO_PATH_URL,
            MARKET_PATH_URL,
            MARKET_PRICE_PATH_URL,
            SNAPSHOT_PATH_URL,
            TRADES_PATH_URL,
            ORDERS_PATH_URL,
            ORDER_BY_ID_PATH_URL,
            ORDER_TRADES_PATH_URL,
            POSITIONS_PATH_URL,
            USER_TRADES_PATH_URL,
            CANCEL_ALL_PATH_URL,
        ]
    ],
]

# ---------------------------------------------------------------------------
# Error codes the connector matches against
# ---------------------------------------------------------------------------

ORDER_NOT_EXIST_ERROR_CODE = "NOT_FOUND"
ORDER_NOT_EXIST_MESSAGE = "Order not found"

DUPLICATE_CLIENT_ORDER_ID_CODE = "DUPLICATE_CLIENT_ORDER_ID"

INSUFFICIENT_BALANCE_CODE = "INSUFFICIENT_BALANCE"

# ---------------------------------------------------------------------------
# Polling cadences (REST-only world)
# ---------------------------------------------------------------------------
# The connector overrides Hummingbot's default WS subscribe loops with REST
# pollers at these rates.

ORDER_BOOK_SNAPSHOT_POLL_INTERVAL = 0.5     # 500ms — driver for quoting
TRADE_TAPE_POLL_INTERVAL = 1.0              # 1s
USER_OPEN_ORDERS_POLL_INTERVAL = 1.0        # 1s — fill / status detection
USER_BALANCES_POLL_INTERVAL = 5.0           # 5s
SERVER_TIME_POLL_INTERVAL = 300.0           # 5min — clock-drift correction

# ---------------------------------------------------------------------------
# Server-side page-size clamps (mirror the server's limits; if we ask for
# more, the server silently caps).
# ---------------------------------------------------------------------------

ORDERS_MAX_PAGE_SIZE = 30                   # /orders (open=true and otherwise)
TRADES_MAX_PAGE_SIZE = 24                   # /markets/:ticker/trades + /users/me/trades

# Cancel confirmation: KalqiX processes a cancel asynchronously (the DELETE is
# acked, then the engine settles it within tens of ms). GET /orders/{id} reflects
# `CANCELLATION_REQUESTED` immediately and then the terminal state, so we poll it
# a few times right after the DELETE to confirm the real outcome (CANCELLED vs a
# fill that raced the cancel) instead of waiting for the slow status-poll loop.
CANCEL_CONFIRM_MAX_POLLS = 3
CANCEL_CONFIRM_DELAY = 0.05

# Hard cap on pages walked per poll cycle. Defensive — under normal load
# the pollers exit early on the first short page. Bound the worst case so
# a runaway response or a clock skew can't burn the rate-limit bucket.
MAX_PAGES_PER_POLL = 20
