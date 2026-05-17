from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import OrderState

# A single source of truth for constant variables related to the exchange.
#
# Drift Protocol is a Solana perpetual DEX. Hummingbot integrates via the
# self-hosted **Drift Gateway** (https://github.com/drift-labs/gateway),
# which holds the signing keypair (DRIFT_GATEWAY_KEY env) and exposes a
# REST + WebSocket API — clients do NOT authenticate to the gateway
# itself (same architecture as dydx_v4_perpetual / injective_v2). Order
# book data is served by Drift's hosted DLOB server.

EXCHANGE_NAME = "drift_perpetual"
DEFAULT_DOMAIN = "mainnet"

API_VERSION = "v2"
CURRENCY = "USDC"
MARKET_TYPE_PERP = "perp"

HBOT_BROKER_ID = "Hummingbot"
MAX_ID_LEN = 36
HEARTBEAT_INTERVAL = 30.0

# --- Base URLs ---
# Gateway is self-hosted by the operator. Default bind is 127.0.0.1:8080
# (REST) and 127.0.0.1:1337 (WS, configurable via --ws-port). These are
# overridable through the connector config (see drift_perpetual_utils).
DRIFT_GATEWAY_DEFAULT_HOST = "127.0.0.1"
DRIFT_GATEWAY_DEFAULT_REST_PORT = 8080
DRIFT_GATEWAY_DEFAULT_WS_PORT = 1337

DRIFT_GATEWAY_REST_URL = "http://{host}:{port}/{version}".format(
    host=DRIFT_GATEWAY_DEFAULT_HOST, port=DRIFT_GATEWAY_DEFAULT_REST_PORT, version=API_VERSION
)
DRIFT_GATEWAY_WS_URL = "ws://{host}:{port}".format(
    host=DRIFT_GATEWAY_DEFAULT_HOST, port=DRIFT_GATEWAY_DEFAULT_WS_PORT
)

# Hosted DLOB server (order book + auction params). Public, read-only.
DRIFT_DLOB_REST_URL = "https://dlob.drift.trade"
DRIFT_DLOB_WS_URL = "wss://dlob.drift.trade/ws"

# Hosted Data API (historical funding rates).
DRIFT_DATA_API_URL = "https://data.api.drift.trade"

# --- Gateway REST paths (relative to DRIFT_GATEWAY_REST_URL) ---
PATH_MARKETS = "/markets"                       # GET  spot+perp market metadata
PATH_MARKET_INFO = "/marketInfo"                # GET  /marketInfo/{marketIndex}
PATH_ORDERS = "/orders"                         # GET / POST / PATCH / DELETE
PATH_CANCEL_AND_PLACE = "/orders/cancelAndPlace"  # atomic cancel+place
PATH_POSITIONS = "/positions"                   # GET  all positions
PATH_POSITION_INFO = "/positionInfo"            # GET  /positionInfo/{marketIndex}
PATH_BALANCE = "/balance"                       # GET  SOL balance of signer
PATH_COLLATERAL = "/collateral"                 # GET  total/free maint. collateral
PATH_LEVERAGE = "/leverage"                     # GET / POST
PATH_MARGIN_INFO = "/marginInfo"                # GET  margin requirements
PATH_AUTHORITY = "/authority"                   # GET  signer public key
PATH_TRANSACTION_EVENT = "/transactionEvent"    # GET  /transactionEvent/{signature}

# --- DLOB paths (relative to DRIFT_DLOB_REST_URL) ---
PATH_DLOB_L2 = "/l2"                            # aggregated order book snapshot
PATH_DLOB_L3 = "/l3"                            # per-order detail
PATH_DLOB_TOP_MAKERS = "/topMakers"
PATH_DLOB_AUCTION_PARAMS = "/auctionParams"

# --- Data API paths (relative to DRIFT_DATA_API_URL) ---
# VERIFIED 2026-05-17 against the live Data API: the docs' documented
# `/fundingRates?marketName=` route 404s ("Cannot GET /fundingRates");
# the real route is market-scoped path-param style. Response envelope:
#   {"success": true, "records": [ {...}, ... ]}   (records newest-first)
# Each record carries ALREADY-DESCALED decimal strings, e.g.
# fundingRate="-0.001024958", oraclePriceTwap="84.69" — the on-chain
# *_PRECISION scales below are NOT applied to Data API responses (they
# apply only to raw on-chain / DLOB integers).
PATH_FUNDING_RATES_TEMPLATE = "/market/{market}/fundingRates"

# Drift perp funding settles hourly (verified: live record interval
# ~3600s). The DLOB stream carries no funding channel, so market funding
# info is REST-polled from the Data API at this cadence.
FUNDING_RATE_POLL_INTERVAL = 600

# --- Gateway WebSocket channels ---
# Subscribe shape: {"method": "subscribe", "subAccountId": 0}
WS_METHOD_SUBSCRIBE = "subscribe"
WS_METHOD_UNSUBSCRIBE = "unsubscribe"
WS_CHANNEL_ORDERS = "orders"          # OrderCreate / OrderCancel / OrderExpire / OrderCancelMissing
WS_CHANNEL_FILLS = "fills"            # trade execution w/ maker/taker
WS_CHANNEL_FUNDING = "funding"        # funding payment settlements (perps)

# DLOB WS (order book stream).
# Verified subscribe shape (drift-labs/dlob-server example/wsClient.ts):
#   {"type":"subscribe","marketType":"perp","channel":"orderbook","market":"SOL-PERP"}
WS_DLOB_TYPE_SUBSCRIBE = "subscribe"
WS_DLOB_CHANNEL_ORDERBOOK = "orderbook"
WS_DLOB_CHANNEL_TRADES = "trades"

# --- Numeric precision (verified: driftpy constants/numeric_constants.py) ---
# DLOB L2 levels and on-chain figures are integers scaled by these.
PRICE_PRECISION = 1_000_000           # 1e6
BASE_PRECISION = 1_000_000_000        # 1e9
QUOTE_PRECISION = 1_000_000           # 1e6
FUNDING_RATE_PRECISION = 1_000_000_000  # 1e9 (PRICE_PRECISION * 1e3)

# --- Order semantics ---
ORDER_TYPE_MAP = {
    OrderType.LIMIT: "limit",
    OrderType.LIMIT_MAKER: "limit",
    OrderType.MARKET: "market",
}

# Gateway transactionEvent / order-stream status strings → Hummingbot OrderState
ORDER_STATE = {
    "OrderCreate": OrderState.OPEN,
    "Open": OrderState.OPEN,
    "PartialFill": OrderState.PARTIALLY_FILLED,
    "Fill": OrderState.FILLED,
    "Filled": OrderState.FILLED,
    "OrderCancel": OrderState.CANCELED,
    "Canceled": OrderState.CANCELED,
    "OrderExpire": OrderState.CANCELED,
    "OrderCancelMissing": OrderState.FAILED,
}

# --- Rate limits ---
# Drift Gateway runs locally (operator-hosted) so the practical limiter is
# the upstream Solana RPC + DLOB/Data API. Drift does not publish hard
# numeric limits; these are conservative defaults mirroring the pattern
# used by other gateway-style connectors and are tunable post-integration.
RATE_LIMIT_ID_ALL = "all"
RATE_LIMITS = [
    RateLimit(limit_id=RATE_LIMIT_ID_ALL, limit=600, time_interval=60),
]
