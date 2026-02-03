"""
Constants for Deluthium DEX connector.

Deluthium (DarkPool) is an RFQ-based DEX that provides swap quotes and
on-chain execution across BSC, Base, and Ethereum chains.
"""

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "deluthium"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = 36  # UUID length

# Domain settings
DOMAIN = EXCHANGE_NAME
DEFAULT_DOMAIN = "deluthium"

# API Base URLs
BASE_URL = "https://rfq-api.deluthium.ai"

# Supported Chain IDs
CHAIN_IDS = {
    "bsc": 56,
    "base": 8453,
    "ethereum": 1,
}

DEFAULT_CHAIN_ID = 56  # BSC

# Wrapped token addresses per chain (for native token handling)
WRAPPED_TOKENS = {
    56: "0xBB4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",    # WBNB on BSC
    8453: "0x4200000000000000000000000000000000000006",  # WETH on Base
    1: "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",    # WETH on Ethereum
}

# Native token represented as zero address
NATIVE_TOKEN_ADDRESS = "0x0000000000000000000000000000000000000000"

# REST API Endpoints
LISTING_PAIRS_URL = "/v1/listing/pairs"
LISTING_TOKENS_URL = "/v1/listing/tokens"
MARKET_PAIR_URL = "/v1/market/pair"
MARKET_KLINES_URL = "/v1/market/klines"
QUOTE_INDICATIVE_URL = "/v1/quote/indicative"
QUOTE_FIRM_URL = "/v1/quote/firm"

# Endpoint names for rate limiting
ALL_ENDPOINTS_LIMIT = "All"

# K-line/OHLCV intervals
TIMEFRAMES = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "8h": "8h",
    "12h": "12h",
    "1d": "1d",
    "3d": "3d",
    "1w": "1w",
    "1M": "1M",
}

# Order states mapping
# Note: Deluthium is RFQ-based, so orders are created and immediately
# return calldata for on-chain execution. There's no traditional order lifecycle.
ORDER_STATE = {
    "pending": OrderState.PENDING_CREATE,
    "created": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "canceled": OrderState.CANCELED,
    "expired": OrderState.CANCELED,
    "failed": OrderState.FAILED,
}

# Error messages
ORDER_NOT_EXIST_MESSAGE = "order not found"
UNKNOWN_ORDER_MESSAGE = "Order does not exist"

# Heartbeat and polling intervals
HEARTBEAT_TIME_INTERVAL = 30.0
SHORT_POLL_INTERVAL = 5.0
LONG_POLL_INTERVAL = 120.0

# Rate limits (conservative estimates)
# Deluthium doesn't document specific rate limits, using reasonable defaults
MAX_REQUEST = 300
RATE_LIMIT_INTERVAL = 60  # seconds

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=MAX_REQUEST, time_interval=RATE_LIMIT_INTERVAL),
    # Listing endpoints
    RateLimit(
        limit_id=LISTING_PAIRS_URL,
        limit=MAX_REQUEST,
        time_interval=RATE_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]
    ),
    RateLimit(
        limit_id=LISTING_TOKENS_URL,
        limit=MAX_REQUEST,
        time_interval=RATE_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]
    ),
    # Market data endpoints
    RateLimit(
        limit_id=MARKET_PAIR_URL,
        limit=MAX_REQUEST,
        time_interval=RATE_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]
    ),
    RateLimit(
        limit_id=MARKET_KLINES_URL,
        limit=MAX_REQUEST,
        time_interval=RATE_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]
    ),
    # Trading endpoints
    RateLimit(
        limit_id=QUOTE_INDICATIVE_URL,
        limit=MAX_REQUEST,
        time_interval=RATE_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]
    ),
    RateLimit(
        limit_id=QUOTE_FIRM_URL,
        limit=MAX_REQUEST,
        time_interval=RATE_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]
    ),
]

# Success code for API responses
SUCCESS_CODE = 10000

# String error codes (Trading Service)
STRING_ERROR_CODES = {
    "INVALID_INPUT": "BadRequest",
    "INVALID_TOKEN": "BadSymbol",
    "INVALID_AMOUNT": "InvalidOrder",
    "INVALID_PAIR": "BadSymbol",
    "INVALID_DEADLINE": "InvalidOrder",
    "QUOTE_EXPIRED": "OrderNotFound",
    "INSUFFICIENT_LIQUIDITY": "InsufficientFunds",
    "MM_NOT_AVAILABLE": "ExchangeNotAvailable",
    "NO_QUOTES": "ExchangeError",
    "SLIPPAGE_EXCEEDED": "InvalidOrder",
    "INTERNAL_ERROR": "ExchangeError",
    "SIGNING_ERROR": "AuthenticationError",
    "TIMEOUT_ERROR": "RequestTimeout",
    "DATABASE_ERROR": "ExchangeError",
    "REDIS_ERROR": "ExchangeError",
    "KAFKA_ERROR": "ExchangeError",
    "MM_REQUEST_ERROR": "ExchangeError",
    "MM_SIGNATURE_ERROR": "ExchangeError",
    "MM_NOT_FOUND": "ExchangeError",
}

# Numeric error codes (Market Data Service)
NUMERIC_ERROR_CODES = {
    10000: None,  # Success
    10095: "BadRequest",  # Invalid parameters
    20003: "ExchangeError",  # Internal service error
    20004: "BadSymbol",  # Not found (pair not found)
}

# Default slippage for RFQ orders (percentage)
DEFAULT_SLIPPAGE = 0.5

# Default quote expiry time in seconds
DEFAULT_EXPIRY_TIME_SEC = 60
