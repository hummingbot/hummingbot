import sys
from decimal import Decimal

from xrpl.asyncio.transaction.main import _LEDGER_OFFSET

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState, OrderType

# =============================================================================
# Exchange Identification
# =============================================================================
EXCHANGE_NAME = "xrpl"
DOMAIN = "xrpl"  # Placeholder - not used in XRPL connector

# Hummingbot order identification
HBOT_SOURCE_TAG_ID = 19089388
HBOT_ORDER_ID_PREFIX = "hbot"
MAX_ORDER_ID_LEN = 40

# =============================================================================
# Network URLs
# =============================================================================
DEFAULT_JSON_RPC_URL = "https://xrplcluster.com/"
DEFAULT_WSS_URL = "wss://xrplcluster.com/"

# =============================================================================
# WebSocket Event Types
# =============================================================================
TRADE_EVENT_TYPE = "trades"
DIFF_EVENT_TYPE = "diffs"
SNAPSHOT_EVENT_TYPE = "order_book_snapshots"

# =============================================================================
# XRPL Units & Reserves
# =============================================================================
ONE_DROP = Decimal("0.000001")  # Smallest unit of XRP (1 XRP = 1,000,000 drops)
WALLET_RESERVE = Decimal("1")  # Base reserve required to activate a wallet (XRP)
LEDGER_OBJECT_RESERVE = Decimal("0.2")  # Reserve per ledger object (XRP)

# =============================================================================
# Order State Mapping
# =============================================================================
ORDER_STATE = {
    "open": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "partial_filled": OrderState.PARTIALLY_FILLED,
    "canceled": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
}

# =============================================================================
# Order Types & Flags
# =============================================================================
# XRPL OfferCreate flags: https://xrpl.org/offercreate.html
XRPL_ORDER_TYPE = {
    OrderType.LIMIT: 65536,  # tfPassive - don't cross existing offers
    OrderType.LIMIT_MAKER: 65536,  # tfPassive - maker only
    OrderType.MARKET: 262144,  # tfImmediateOrCancel - fill or kill
}
XRPL_SELL_FLAG = 524288  # tfSell - treat as sell offer

# =============================================================================
# Order Execution Settings
# =============================================================================
MARKET_ORDER_MAX_SLIPPAGE = Decimal("0.01")  # 1% max slippage for market orders
SIDE_BUY = 0
SIDE_SELL = 1

# =============================================================================
# Order Book Settings
# =============================================================================
ORDER_BOOK_DEPTH = 100  # Number of price levels to fetch
FETCH_ORDER_BOOK_MAX_RETRY = 3
FETCH_ORDER_BOOK_RETRY_INTERVAL = 5  # Seconds between retries

# =============================================================================
# Ledger & Transaction Settings
# =============================================================================
# Ledger offset for order status queries (2x the standard offset for safety)
LEDGER_OFFSET = _LEDGER_OFFSET * 2
XRPL_MAX_DIGIT = 16  # Maximum precision digits for issued currencies

# =============================================================================
# Timeout Configuration (seconds)
# =============================================================================
REQUEST_TIMEOUT = 60  # General request timeout
PENDING_ORDER_STATUS_CHECK_TIMEOUT = 120  # Timeout for pending order status checks
CANCEL_ALL_TIMEOUT = 600  # Timeout for cancel all orders operation

# =============================================================================
# Rate Limiting
# =============================================================================
# NOTE: XRPL connector uses connection pool and worker pool instead of traditional rate limiting
RAW_REQUESTS = "RAW_REQUESTS"
NO_LIMIT = sys.maxsize
RATE_LIMITS = [
    RateLimit(limit_id=RAW_REQUESTS, limit=NO_LIMIT, time_interval=1),
]

# =============================================================================
# Order Placement Retry Configuration
# =============================================================================
PLACE_ORDER_MAX_RETRY = 5
PLACE_ORDER_RETRY_INTERVAL = 5  # Seconds between retries

# Sequence number error handling
# - tefPAST_SEQ: Sequence behind ledger state - autofill will correct
# - terPRE_SEQ: Sequence ahead - prior transactions still in flight
SEQUENCE_ERRORS = ["tefPAST_SEQ", "terPRE_SEQ"]
PRE_SEQ_RETRY_INTERVAL = 5  # Wait for prior transactions to confirm

# Transient errors safe to retry
TRANSIENT_RETRY_ERRORS = ["telCAN_NOT_QUEUE"]

# =============================================================================
# Transaction Submission Pipeline
# =============================================================================
# All submissions are serialized to prevent sequence number race conditions
PIPELINE_SUBMISSION_DELAY_MS = 350  # Delay between submissions (milliseconds)
PIPELINE_MAX_QUEUE_SIZE = 500  # Maximum pending submissions in queue
FEE_MULTIPLIER = 3  # Multiplier for transaction fees (ensures priority)

# =============================================================================
# Cancel Order Retry Configuration
# =============================================================================
CANCEL_MAX_RETRY = 5
CANCEL_RETRY_INTERVAL = 5  # Seconds between retries

# =============================================================================
# Transaction Verification Retry Configuration
# =============================================================================
VERIFY_TRANSACTION_MAX_RETRY = 5
VERIFY_TRANSACTION_RETRY_INTERVAL = 5  # Seconds between retries
AUTOFILL_TRANSACTION_MAX_RETRY = 5

# =============================================================================
# Polling & Refresh Intervals (seconds)
# =============================================================================
REQUEST_RETRY_INTERVAL = 5  # General request retry interval
REQUEST_ORDERBOOK_INTERVAL = 10  # Order book refresh interval
CLIENT_REFRESH_INTERVAL = 30  # Client connection refresh interval

# =============================================================================
# WebSocket Configuration
# =============================================================================
WEBSOCKET_MAX_SIZE_BYTES = 2**22  # 4 MB max message size
WEBSOCKET_CONNECTION_TIMEOUT = 30  # Connection timeout (seconds)

# =============================================================================
# Connection Pool Configuration
# =============================================================================
CONNECTION_POOL_HEALTH_CHECK_INTERVAL = 30.0  # Seconds between health checks
CONNECTION_POOL_MAX_AGE = 300.0  # Max connection age before refresh (seconds)
CONNECTION_POOL_TIMEOUT = 30.0  # Connection timeout (seconds)
CONNECTION_MAX_CONSECUTIVE_ERRORS = 3  # Errors before marking unhealthy
PROACTIVE_PING_INTERVAL = 20.0  # Seconds between proactive pings

# =============================================================================
# Worker Pool Configuration
# =============================================================================
# Timeouts for different operation types (seconds)
WORKER_DEFAULT_TIMEOUT = 60.0  # Default request timeout
SUBMIT_TX_TIMEOUT = 30.0  # Transaction submission timeout
VERIFY_TX_TIMEOUT = 120.0  # Transaction verification timeout
VERIFY_TX_FALLBACK_TIMEOUT = 15.0  # Fallback ledger query timeout (5 attempts × 3s)
QUERY_TIMEOUT = 30.0  # Query timeout
CANCEL_TX_TIMEOUT = 30.0  # Cancel transaction timeout

# Worker pool sizing
QUERY_WORKER_POOL_SIZE = 1  # Concurrent query workers
VERIFICATION_WORKER_POOL_SIZE = 1  # Concurrent verification workers
TX_WORKER_POOL_SIZE = 1  # Concurrent transaction workers (per wallet)

# Worker pool behavior
WORKER_TASK_TIMEOUT = 30.0  # Individual task processing timeout (seconds)
WORKER_MAX_QUEUE_TIME = 300.0  # Max queue wait before task expires (seconds)
WORKER_CLIENT_RETRY_TIMEOUT = 10.0  # Wait time for healthy client (seconds)
WORKER_CLIENT_RECONNECT_ATTEMPTS = 5  # Reconnect attempts before getting new client
WORKER_POOL_TASK_QUEUE_SIZE = 100  # Max pending tasks per pool

# =============================================================================
# Polling Data Source Configuration
# =============================================================================
POLLING_INTERVAL = 5.0  # Account state poll interval (seconds)
SEEN_TX_HASHES_MAX_SIZE = 1000  # Max transaction hashes for deduplication

# =============================================================================
# Order Book Subscription Configuration
# =============================================================================
SUBSCRIPTION_CONNECTION_TIMEOUT = 30.0  # Connection creation timeout (seconds)
SUBSCRIPTION_RECONNECT_DELAY = 5.0  # Delay between reconnect attempts (seconds)
SUBSCRIPTION_MAX_RETRIES = 10  # Max consecutive reconnect attempts
SUBSCRIPTION_STALE_TIMEOUT = 60.0  # Force reconnect if no messages (seconds)
SUBSCRIPTION_HEALTH_CHECK_INTERVAL = 15.0  # Health check interval (seconds)

# =============================================================================
# Supported Markets
# =============================================================================
MARKETS = {
    "XRP-RLUSD": {
        "base": "XRP",
        "quote": "RLUSD",
        "base_issuer": "",
        "quote_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
    },
    "XRP-IBTC": {
        "base": "XRP",
        "quote": "iBTC",
        "base_issuer": "",
        "quote_issuer": "rGcyRGrZPaJAZbZDi4NqRFLA5GQH63iFpD",
    },
    "XRP-USDC": {
        "base": "XRP",
        "quote": "USDC",
        "base_issuer": "",
        "quote_issuer": "rGm7WCVp9gb4jZHWTEtGUr4dd74z2XuWhE",
    },
    "IBTC-RLUSD": {
        "base": "iBTC",
        "quote": "RLUSD",
        "base_issuer": "rGcyRGrZPaJAZbZDi4NqRFLA5GQH63iFpD",
        "quote_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
    },
    "XRP-USD": {
        "base": "XRP",
        "quote": "USD",
        "base_issuer": "",
        "quote_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
    },
    "XRP-EUR": {
        "base": "XRP",
        "quote": "EUR",
        "base_issuer": "",
        "quote_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
    },
    "XRP-GBP": {
        "base": "XRP",
        "quote": "GBP",
        "base_issuer": "",
        "quote_issuer": "r4GN9eEoz9K4BhMQXe4H1eYNtvtkwGdt8g",
    },
    "XRP-BTC": {
        "base": "XRP",
        "quote": "BTC",
        "base_issuer": "",
        "quote_issuer": "rchGBxcD1A1C2tdxF6papQYZ8kjRKMYcL",
    },
    "XRP-ETH": {
        "base": "XRP",
        "quote": "ETH",
        "base_issuer": "",
        "quote_issuer": "rcA8X3TVMST1n3CJeAdGk1RdRCHii7N2h",
    },
    "XRP-LTC": {
        "base": "XRP",
        "quote": "LTC",
        "base_issuer": "",
        "quote_issuer": "rcRzGWq6Ng3jeYhqnmM4zcWcUh69hrQ8V",
    },
    "XRP-CNY": {
        "base": "XRP",
        "quote": "CNY",
        "base_issuer": "",
        "quote_issuer": "rKiCet8SdvWxPXnAgYarFUXMh1zCPz432Y",
    },
    "XRP-BCH": {
        "base": "XRP",
        "quote": "BCH",
        "base_issuer": "",
        "quote_issuer": "rcyS4CeCZVYvTiKcxj6Sx32ibKwcDHLds",
    },
    "XRP-ETC": {
        "base": "XRP",
        "quote": "ETC",
        "base_issuer": "",
        "quote_issuer": "rDAN8tzydyNfnNf2bfUQY6iR96UbpvNsze",
    },
    "XRP-DSH": {
        "base": "XRP",
        "quote": "DSH",
        "base_issuer": "",
        "quote_issuer": "rcXY84C4g14iFp6taFXjjQGVeHqSCh9RX",
    },
    "XRP-XAU": {
        "base": "XRP",
        "quote": "XAU",
        "base_issuer": "",
        "quote_issuer": "rcoef87SYMJ58NAFx7fNM5frVknmvHsvJ",
    },
    "XRP-SGB": {
        "base": "XRP",
        "quote": "SGB",
        "base_issuer": "",
        "quote_issuer": "rctArjqVvTHihekzDeecKo6mkTYTUSBNc",
    },
    "XRP-USDT": {
        "base": "XRP",
        "quote": "USDT",
        "base_issuer": "",
        "quote_issuer": "rcvxE9PS9YBwxtGg1qNeewV6ZB3wGubZq",
    },
    "XRP-WXRP": {
        "base": "XRP",
        "quote": "WXRP",
        "base_issuer": "",
        "quote_issuer": "rEa5QY8tdbjgitLyfKF1E5Qx3VGgvbUhB3",
    },
    "XRP-GALA": {
        "base": "XRP",
        "quote": "GALA",
        "base_issuer": "",
        "quote_issuer": "rf5YPb9y9P3fTjhxNaZqmrwaj5ar8PG1gM",
    },
    "XRP-FLR": {
        "base": "XRP",
        "quote": "FLR",
        "base_issuer": "",
        "quote_issuer": "rcxJwVnftZzXqyH9YheB8TgeiZUhNo1Eu",
    },
    "XRP-XAH": {
        "base": "XRP",
        "quote": "XAH",
        "base_issuer": "",
        "quote_issuer": "rswh1fvyLqHizBS2awu1vs6QcmwTBd9qiv",
    },
    "USD-XRP": {
        "base": "USD",
        "quote": "XRP",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "",
    },
    "USD-EUR": {
        "base": "USD",
        "quote": "EUR",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
    },
    "USD-GBP": {
        "base": "USD",
        "quote": "GBP",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "r4GN9eEoz9K4BhMQXe4H1eYNtvtkwGdt8g",
    },
    "USD-BTC": {
        "base": "USD",
        "quote": "BTC",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "rchGBxcD1A1C2tdxF6papQYZ8kjRKMYcL",
    },
    "USD-BCH": {
        "base": "USD",
        "quote": "BCH",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "rcyS4CeCZVYvTiKcxj6Sx32ibKwcDHLds",
    },
    "USD-LTC": {
        "base": "USD",
        "quote": "LTC",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "rcRzGWq6Ng3jeYhqnmM4zcWcUh69hrQ8V",
    },
    "USD.b-XRP": {
        "base": "USD",
        "quote": "XRP",
        "base_issuer": "rvYAfWj5gh67oV6fW32ZzP3Aw4Eubs59B",
        "quote_issuer": "",
    },
    "USD-USDT": {
        "base": "USD",
        "quote": "USDT",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "rcvxE9PS9YBwxtGg1qNeewV6ZB3wGubZq",
    },
    "USD-USDC": {
        "base": "USD",
        "quote": "USDC",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "rGm7WCVp9gb4jZHWTEtGUr4dd74z2XuWhE",
    },
    "USD-WXRP": {
        "base": "USD",
        "quote": "WXRP",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "rEa5QY8tdbjgitLyfKF1E5Qx3VGgvbUhB3",
    },
    "USD-GALA": {
        "base": "USD",
        "quote": "GALA",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "rf5YPb9y9P3fTjhxNaZqmrwaj5ar8PG1gM",
    },
    "USD-FLR": {
        "base": "USD",
        "quote": "FLR",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "rcxJwVnftZzXqyH9YheB8TgeiZUhNo1Eu",
    },
    "EUR-XRP": {
        "base": "EUR",
        "quote": "XRP",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "",
    },
    "EUR-USD": {
        "base": "EUR",
        "quote": "USD",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
    },
    "EUR-GBP": {
        "base": "EUR",
        "quote": "GBP",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "r4GN9eEoz9K4BhMQXe4H1eYNtvtkwGdt8g",
    },
    "EUR-USD.b": {
        "base": "EUR",
        "quote": "USD",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "rvYAfWj5gh67oV6fW32ZzP3Aw4Eubs59B",
    },
    "EUR-BTC": {
        "base": "EUR",
        "quote": "BTC",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "rchGBxcD1A1C2tdxF6papQYZ8kjRKMYcL",
    },
    "EUR-BCH": {
        "base": "EUR",
        "quote": "BCH",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "rcyS4CeCZVYvTiKcxj6Sx32ibKwcDHLds",
    },
    "EUR-LTC": {
        "base": "EUR",
        "quote": "LTC",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "rcRzGWq6Ng3jeYhqnmM4zcWcUh69hrQ8V",
    },
    "EUR-USDT": {
        "base": "EUR",
        "quote": "USDT",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "rcvxE9PS9YBwxtGg1qNeewV6ZB3wGubZq",
    },
    "EUR-USDC": {
        "base": "EUR",
        "quote": "USDC",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "rGm7WCVp9gb4jZHWTEtGUr4dd74z2XuWhE",
    },
    "EUR-WXRP": {
        "base": "EUR",
        "quote": "WXRP",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "rEa5QY8tdbjgitLyfKF1E5Qx3VGgvbUhB3",
    },
    "EUR-GALA": {
        "base": "EUR",
        "quote": "GALA",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "rf5YPb9y9P3fTjhxNaZqmrwaj5ar8PG1gM",
    },
    "EUR-FLR": {
        "base": "EUR",
        "quote": "FLR",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "rcxJwVnftZzXqyH9YheB8TgeiZUhNo1Eu",
    },
    "SGB-XRP": {
        "base": "SGB",
        "quote": "XRP",
        "base_issuer": "rctArjqVvTHihekzDeecKo6mkTYTUSBNc",
        "quote_issuer": "",
    },
    "ELS-XRP": {
        "base": "ELS",
        "quote": "XRP",
        "base_issuer": "rHXuEaRYnnJHbDeuBH5w8yPh5uwNVh5zAg",
        "quote_issuer": "",
    },
    "USDT-XRP": {
        "base": "USDT",
        "quote": "XRP",
        "base_issuer": "rcvxE9PS9YBwxtGg1qNeewV6ZB3wGubZq",
        "quote_issuer": "",
    },
    "USDC-XRP": {
        "base": "USDC",
        "quote": "XRP",
        "base_issuer": "rGm7WCVp9gb4jZHWTEtGUr4dd74z2XuWhE",
        "quote_issuer": "",
    },
    "SOLO-XRP": {
        "base": "SOLO",
        "quote": "XRP",
        "base_issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
        "quote_issuer": "",
    },
    "WXRP-XRP": {
        "base": "WXRP",
        "quote": "XRP",
        "base_issuer": "rEa5QY8tdbjgitLyfKF1E5Qx3VGgvbUhB3",
        "quote_issuer": "",
    },
    "GALA-XRP": {
        "base": "GALA",
        "quote": "XRP",
        "base_issuer": "rf5YPb9y9P3fTjhxNaZqmrwaj5ar8PG1gM",
        "quote_issuer": "",
    },
    "FLR-XRP": {
        "base": "FLR",
        "quote": "XRP",
        "base_issuer": "rcxJwVnftZzXqyH9YheB8TgeiZUhNo1Eu",
        "quote_issuer": "",
    },
    "SOLO-USD": {
        "base": "SOLO",
        "quote": "USD",
        "base_issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
        "quote_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
    },
    "SOLO-USD.b": {
        "base": "SOLO",
        "quote": "USD",
        "base_issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
        "quote_issuer": "rvYAfWj5gh67oV6fW32ZzP3Aw4Eubs59B",
    },
    "ICOIN-XRP": {
        "base": "icoin",
        "quote": "XRP",
        "base_issuer": "rJSTh1VLk52tFC3VRXkNWu7Q4nYmfZv7BZ",
        "quote_issuer": "",
    },
    "CORE-XRP": {
        "base": "CORE",
        "quote": "XRP",
        "base_issuer": "rcoreNywaoz2ZCQ8Lg2EbSLnGuRBmun6D",
        "quote_issuer": "",
    },
    "XMEME-XRP": {
        "base": "XMEME",
        "quote": "XRP",
        "base_issuer": "r4UPddYeGeZgDhSGPkooURsQtmGda4oYQW",
        "quote_issuer": "",
    },
    "CSC-XRP": {
        "base": "CSC",
        "quote": "XRP",
        "base_issuer": "rCSCManTZ8ME9EoLrSHHYKW8PPwWMgkwr",
        "quote_issuer": "",
    },
    "FURY-XRP": {
        "base": "FURY",
        "quote": "XRP",
        "base_issuer": "rnoKi9s9b6WYaNGWQy4qVdnKo6Lj2eHE1D",
        "quote_issuer": "",
    },
    "XSPECTAR-XRP": {
        "base": "xSPECTAR",
        "quote": "XRP",
        "base_issuer": "rh5jzTCdMRCVjQ7LT6zucjezC47KATkuvv",
        "quote_issuer": "",
    },
    "RPR-XRP": {
        "base": "RPR",
        "quote": "XRP",
        "base_issuer": "r3qWgpz2ry3BhcRJ8JE6rxM8esrfhuKp4R",
        "quote_issuer": "",
    },
    "XRDOGE-XRP": {
        "base": "XRdoge",
        "quote": "XRP",
        "base_issuer": "rLqUC2eCPohYvJCEBJ77eCCqVL2uEiczjA",
        "quote_issuer": "",
    },
    "EQUILIBRIUM-XRP": {
        "base": "Equilibrium",
        "quote": "XRP",
        "base_issuer": "rpakCr61Q92abPXJnVboKENmpKssWyHpwu",
        "quote_issuer": "",
    },
    "RLUSD-XRP": {
        "base": "RLUSD",
        "quote": "XRP",
        "base_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
        "quote_issuer": "",
    },
    "RLUSD-USD": {
        "base": "RLUSD",
        "quote": "USD",
        "base_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
        "quote_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
    },
    "USD-RLUSD": {
        "base": "USD",
        "quote": "RLUSD",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
    },
    "RLUSD-EUR": {
        "base": "RLUSD",
        "quote": "EUR",
        "base_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
        "quote_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
    },
    "EUR-RLUSD": {
        "base": "EUR",
        "quote": "RLUSD",
        "base_issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "quote_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
    },
    "RLUSD-USDT": {
        "base": "RLUSD",
        "quote": "USDT",
        "base_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
        "quote_issuer": "rcvxE9PS9YBwxtGg1qNeewV6ZB3wGubZq",
    },
    "USDT-RLUSD": {
        "base": "USDT",
        "quote": "RLUSD",
        "base_issuer": "rcvxE9PS9YBwxtGg1qNeewV6ZB3wGubZq",
        "quote_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
    },
    "RLUSD-USDC": {
        "base": "RLUSD",
        "quote": "USDC",
        "base_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
        "quote_issuer": "rGm7WCVp9gb4jZHWTEtGUr4dd74z2XuWhE",
    },
    "USDC-RLUSD": {
        "base": "USDC",
        "quote": "RLUSD",
        "base_issuer": "rGm7WCVp9gb4jZHWTEtGUr4dd74z2XuWhE",
        "quote_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
    },
    "RLUSD-BTC": {
        "base": "RLUSD",
        "quote": "BTC",
        "base_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
        "quote_issuer": "rchGBxcD1A1C2tdxF6papQYZ8kjRKMYcL",
    },
    "BTC-RLUSD": {
        "base": "BTC",
        "quote": "RLUSD",
        "base_issuer": "rchGBxcD1A1C2tdxF6papQYZ8kjRKMYcL",
        "quote_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
    },
    "RLUSD-ETH": {
        "base": "RLUSD",
        "quote": "ETH",
        "base_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
        "quote_issuer": "rcA8X3TVMST1n3CJeAdGk1RdRCHii7N2h",
    },
    "ETH-RLUSD": {
        "base": "ETH",
        "quote": "RLUSD",
        "base_issuer": "rcA8X3TVMST1n3CJeAdGk1RdRCHii7N2h",
        "quote_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
    },
    "RLUSD-LTC": {
        "base": "RLUSD",
        "quote": "LTC",
        "base_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
        "quote_issuer": "rcRzGWq6Ng3jeYhqnmM4zcWcUh69hrQ8V",
    },
    "LTC-RLUSD": {
        "base": "LTC",
        "quote": "RLUSD",
        "base_issuer": "rcRzGWq6Ng3jeYhqnmM4zcWcUh69hrQ8V",
        "quote_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
    },
    "RLUSD-BCH": {
        "base": "RLUSD",
        "quote": "BCH",
        "base_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
        "quote_issuer": "rcyS4CeCZVYvTiKcxj6Sx32ibKwcDHLds",
    },
    "BCH-RLUSD": {
        "base": "BCH",
        "quote": "RLUSD",
        "base_issuer": "rcyS4CeCZVYvTiKcxj6Sx32ibKwcDHLds",
        "quote_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
    },
    "RLUSD-GBP": {
        "base": "RLUSD",
        "quote": "GBP",
        "base_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
        "quote_issuer": "r4GN9eEoz9K4BhMQXe4H1eYNtvtkwGdt8g",
    },
    "GBP-RLUSD": {
        "base": "GBP",
        "quote": "RLUSD",
        "base_issuer": "r4GN9eEoz9K4BhMQXe4H1eYNtvtkwGdt8g",
        "quote_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
    },
    "RLUSD-WXRP": {
        "base": "RLUSD",
        "quote": "WXRP",
        "base_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
        "quote_issuer": "rEa5QY8tdbjgitLyfKF1E5Qx3VGgvbUhB3",
    },
    "WXRP-RLUSD": {
        "base": "WXRP",
        "quote": "RLUSD",
        "base_issuer": "rEa5QY8tdbjgitLyfKF1E5Qx3VGgvbUhB3",
        "quote_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
    },
    "RLUSD-SOLO": {
        "base": "RLUSD",
        "quote": "SOLO",
        "base_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
        "quote_issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
    },
    "SOLO-RLUSD": {
        "base": "SOLO",
        "quote": "RLUSD",
        "base_issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
        "quote_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
    },
    "RLUSD-GALA": {
        "base": "RLUSD",
        "quote": "GALA",
        "base_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
        "quote_issuer": "rf5YPb9y9P3fTjhxNaZqmrwaj5ar8PG1gM",
    },
    "GALA-RLUSD": {
        "base": "GALA",
        "quote": "RLUSD",
        "base_issuer": "rf5YPb9y9P3fTjhxNaZqmrwaj5ar8PG1gM",
        "quote_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
    },
    "RLUSD-FLR": {
        "base": "RLUSD",
        "quote": "FLR",
        "base_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
        "quote_issuer": "rcxJwVnftZzXqyH9YheB8TgeiZUhNo1Eu",
    },
    "FLR-RLUSD": {
        "base": "FLR",
        "quote": "RLUSD",
        "base_issuer": "rcxJwVnftZzXqyH9YheB8TgeiZUhNo1Eu",
        "quote_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
    },
    "RLUSD-XAU": {
        "base": "RLUSD",
        "quote": "XAU",
        "base_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
        "quote_issuer": "rcoef87SYMJ58NAFx7fNM5frVknmvHsvJ",
    },
    "XAU-RLUSD": {
        "base": "XAU",
        "quote": "RLUSD",
        "base_issuer": "rcoef87SYMJ58NAFx7fNM5frVknmvHsvJ",
        "quote_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
    },
    "IBTC-XRP": {
        "base": "iBTC",
        "quote": "XRP",
        "base_issuer": "rGcyRGrZPaJAZbZDi4NqRFLA5GQH63iFpD",
        "quote_issuer": "",
    },
    "IBTC-USDC": {
        "base": "iBTC",
        "quote": "USDC",
        "base_issuer": "rGcyRGrZPaJAZbZDi4NqRFLA5GQH63iFpD",
        "quote_issuer": "rGm7WCVp9gb4jZHWTEtGUr4dd74z2XuWhE",
    },
    "EUROP-RLUSD": {
        "base": "EUROP",
        "quote": "RLUSD",
        "base_issuer": "rMkEuRii9w9uBMQDnWV5AA43gvYZR9JxVK",
        "quote_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
    },
    "RLUSD-EUROP": {
        "base": "RLUSD",
        "quote": "EUROP",
        "base_issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De",
        "quote_issuer": "rMkEuRii9w9uBMQDnWV5AA43gvYZR9JxVK",
    },
    "EUROP-XRP": {
        "base": "EUROP",
        "quote": "XRP",
        "base_issuer": "rMkEuRii9w9uBMQDnWV5AA43gvYZR9JxVK",
        "quote_issuer": "",
    },
    "XRP-EUROP": {
        "base": "XRP",
        "quote": "EUROP",
        "base_issuer": "",
        "quote_issuer": "rMkEuRii9w9uBMQDnWV5AA43gvYZR9JxVK",
    },
}
