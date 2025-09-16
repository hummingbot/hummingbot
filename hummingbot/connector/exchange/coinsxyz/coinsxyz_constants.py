"""
Constants for Coins.xyz Exchange Connector

This module contains all the constants, API endpoints, rate limits, and configuration
values needed for the Coins.xyz exchange integration.
"""

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

# Exchange Configuration
DEFAULT_DOMAIN = "com"
EXCHANGE_NAME = "coinsxyz"

# Order ID Configuration
HBOT_ORDER_ID_PREFIX = "HBOT-COINSXYZ"
MAX_ORDER_ID_LEN = 32

# Base URLs - Updated with actual Coins.xyz API URLs
REST_URL = "https://api.coins.xyz/openapi/"
WSS_URL = "wss://stream.coins.xyz/openapi/ws"

# API Versions
PUBLIC_API_VERSION = "v1"
PRIVATE_API_VERSION = "v1"

# Public API Endpoints
PING_PATH_URL = "/ping"
SERVER_TIME_PATH_URL = "/time"
EXCHANGE_INFO_PATH_URL = "/exchangeInfo"
TICKER_PRICE_CHANGE_PATH_URL = "/ticker/24hr"
TICKER_BOOK_PATH_URL = "/ticker/bookTicker"
PRICES_PATH_URL = "/ticker/price"
SNAPSHOT_PATH_URL = "/depth"
TRADES_PATH_URL = "/trades"
RECENT_TRADES_PATH_URL = "/trades"  # Recent trades endpoint (same as TRADES_PATH_URL)
KLINES_PATH_URL = "/klines"

# Private API Endpoints
ACCOUNTS_PATH_URL = "/account"
ACCOUNT_INFO_PATH_URL = "/account/info"
ORDER_PATH_URL = "/order"
ORDERS_PATH_URL = "/orders"
OPEN_ORDERS_PATH_URL = "/openOrders"
MY_TRADES_PATH_URL = "/myTrades"
USER_STREAM_PATH_URL = "/userDataStream"
ORDER_CANCEL_PATH_URL = "/order"
ORDER_CANCEL_ALL_PATH_URL = "/openOrders"

# WebSocket Heartbeat
WS_HEARTBEAT_TIME_INTERVAL = 30

# Order Parameters
SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

# Time in Force
TIME_IN_FORCE_GTC = "GTC"  # Good Till Cancelled
TIME_IN_FORCE_IOC = "IOC"  # Immediate or Cancel
TIME_IN_FORCE_FOK = "FOK"  # Fill or Kill

# Rate Limit Types
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS = "ORDERS"
ORDERS_24HR = "ORDERS_24HR"
RAW_REQUESTS = "RAW_REQUESTS"

# Rate Limit Time Intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

# Maximum Requests
MAX_REQUEST = 5000

# Order States Mapping (to be updated based on Coins.ph API documentation)
ORDER_STATE = {
    "PENDING": OrderState.PENDING_CREATE,
    "NEW": OrderState.OPEN,
    "OPEN": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "PENDING_CANCEL": OrderState.PENDING_CANCEL,
    "CANCELED": OrderState.CANCELED,
    "CANCELLED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.FAILED,
    "FAILED": OrderState.FAILED,
}

# WebSocket Event Types
DIFF_EVENT_TYPE = "depthUpdate"
TRADE_EVENT_TYPE = "trade"
ORDER_UPDATE_EVENT_TYPE = "executionReport"
BALANCE_UPDATE_EVENT_TYPE = "outboundAccountPosition"

# Error Codes (to be updated based on Coins.ph API documentation)
ORDER_NOT_EXIST_ERROR_CODE = -2013
ORDER_NOT_EXIST_MESSAGE = "Order does not exist"
UNKNOWN_ORDER_ERROR_CODE = -2011
UNKNOWN_ORDER_MESSAGE = "Unknown order sent"
INSUFFICIENT_BALANCE_ERROR_CODE = -2010
INSUFFICIENT_BALANCE_MESSAGE = "Account has insufficient balance"

# Rate Limits Configuration
# Based on official Coins.xyz API documentation: https://docs.coins.ph/xyz/rest-api/#general-api-information
RATE_LIMITS = [
    # Pool Limits - Based on Coins.xyz official limits
    # IP limit: 1200 requests per minute across all /api/* endpoints
    RateLimit(limit_id=REQUEST_WEIGHT, limit=1200, time_interval=ONE_MINUTE),
    # UID limit: 1800 requests per minute across all /api/* endpoints
    RateLimit(limit_id=RAW_REQUESTS, limit=1800, time_interval=ONE_MINUTE),
    # Order rate limits (tracked per IP and UID)
    RateLimit(limit_id=ORDERS, limit=100, time_interval=10 * ONE_SECOND),
    RateLimit(limit_id=ORDERS_24HR, limit=200000, time_interval=ONE_DAY),
    
    # Endpoint Specific Limits - Based on Coins.xyz API weights
    # General endpoints (Weight: 1)
    RateLimit(limit_id=PING_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),

    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),

    # Exchange info (Weight: 1)
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    
    # Market data endpoints - Variable weights based on parameters
    # 24hr ticker: Weight 1 for single symbol, 40 for all symbols
    RateLimit(limit_id=TICKER_PRICE_CHANGE_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),

    # Book ticker: Weight 1 for single symbol, 2 for all symbols
    RateLimit(limit_id=TICKER_BOOK_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),

    # Order book depth: Weight varies by limit (5-100: 1, 200: 5)
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),

    # Recent trades: Weight 1
    RateLimit(limit_id=RECENT_TRADES_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),

    # Klines/Candlestick data: Weight 1
    RateLimit(limit_id=KLINES_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),

    # Price ticker: Weight 1 for single symbol, 2 for all symbols
    RateLimit(limit_id=PRICES_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    
    # Private endpoints
    # Account info (Weight: 10)
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),

    # Order management (Weight: 1 for new/cancel orders)
    RateLimit(limit_id=ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(ORDERS, 1),
                             LinkedLimitWeightPair(ORDERS_24HR, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),

    # Trade history (Weight: 10)
    RateLimit(limit_id=MY_TRADES_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),

    # User data stream (Weight: 1)
    RateLimit(limit_id=USER_STREAM_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
]

# Trading Pair Validation
def is_exchange_information_valid(exchange_info: dict) -> bool:
    """
    Verifies if a trading pair is valid and active on Coins.ph
    
    :param exchange_info: Trading pair information from exchange
    :return: True if valid and tradeable, False otherwise
    """
    return (exchange_info.get("status") == "TRADING" and
            exchange_info.get("isSpotTradingAllowed", False) and
            "SPOT" in exchange_info.get("permissions", []))
