import sys
from decimal import Decimal

from xrpl.asyncio.transaction.main import _LEDGER_OFFSET

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState, OrderType

EXCHANGE_NAME = "xrpl"
DOMAIN = "xrpl"  # This just a placeholder since we don't use domain in xrpl connect at the moment

HBOT_ORDER_ID_PREFIX = "hbot"
MAX_ORDER_ID_LEN = 64

# Base URL
DEFAULT_JSON_RPC_URL = "https://s1.ripple.com:51234/"
DEFAULT_WSS_URL = "wss://s1.ripple.com/"

# Websocket channels
TRADE_EVENT_TYPE = "trades"
DIFF_EVENT_TYPE = "diffs"
SNAPSHOT_EVENT_TYPE = "order_book_snapshots"

# Drop definitions
ONE_DROP = Decimal("0.000001")

# Order States
ORDER_STATE = {
    "open": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "partial_filled": OrderState.PARTIALLY_FILLED,
    "canceled": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
}

# Order Types
XRPL_ORDER_TYPE = {
    OrderType.LIMIT: 524288,
    OrderType.LIMIT_MAKER: 589824,
    OrderType.MARKET: 786432,
}

# Market Order Max Slippage
MARKET_ORDER_MAX_SLIPPAGE = Decimal("0.05")

# Order Side
SIDE_BUY = 0
SIDE_SELL = 1

# Orderbook settings
ORDER_BOOK_DEPTH = 500

# Ledger offset for getting order status:
LEDGER_OFFSET = _LEDGER_OFFSET

# Rate Limits
# NOTE: We don't have rate limits for xrpl at the moment
RAW_REQUESTS = "RAW_REQUESTS"
NO_LIMIT = sys.maxsize
RATE_LIMITS = [
    RateLimit(limit_id=RAW_REQUESTS, limit=NO_LIMIT, time_interval=1),
]

# Markets list
# TODO: Add more markets
# TODO: Load custom markets by connector config
MARKETS = {
    "SOLO-XRP": {
        "base": "SOLO",
        "quote": "XRP",
        "base_issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
        "quote_issuer": "",
    },
    "SOLO-USD": {
        "base": "SOLO",
        "quote": "USD",
        "base_issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
        "quote_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
    },
    "XRP-USD": {
        "base": "XRP",
        "quote": "USD",
        "base_issuer": "",
        "quote_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
    },
}
