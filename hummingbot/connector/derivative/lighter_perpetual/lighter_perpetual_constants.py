# A single source of truth for constant variables related to Lighter Perpetual
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "lighter_perpetual"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = 32

MARKET_ORDER_SLIPPAGE = 0.05

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "lighter_perpetual_testnet"

# Lighter Perpetual API endpoints - mainnet
BASE_URL = "https://mainnet.zklighter.elliot.ai"
TESTNET_BASE_URL = "https://testnet.zklighter.elliot.ai"
# WebSocket base URLs
WS_URL = "wss://mainnet.zklighter.elliot.ai"
TESTNET_WS_URL = "wss://testnet.zklighter.elliot.ai"

FUNDING_RATE_UPDATE_INTERNAL_SECOND = 3600  # Lighter updates funding hourly
CURRENCY = "USDC"

# API Endpoints - Lighter API v1
# Public endpoints
TICKER_PRICE_CHANGE_URL = "/api/v1/markets/stats"
SNAPSHOT_REST_URL = "/api/v1/orderbook"
EXCHANGE_INFO_URL = "/api/v1/markets"
PING_URL = "/api/v1/markets"
FUNDING_RATES_URL = "/api/v1/funding-rates"
MARK_PRICE_URL = "/api/v1/markets/stats"
RECENT_TRADES_URL = "/api/v1/trades"

# Private endpoints
ACCOUNT_INFO_URL = "/api/v1/account"
BALANCE_URL = "/api/v1/account/balance"
POSITIONS_URL = "/api/v1/account/positions"
LEVERAGE_URL = "/api/v1/account/leverage"

# Order endpoints
CANCEL_ORDER_URL = "/api/v1/orders"
CREATE_ORDER_URL = "/api/v1/orders"
ORDER_URL = "/api/v1/orders"
OPEN_ORDERS_URL = "/api/v1/orders"
ACCOUNT_TRADE_LIST_URL = "/api/v1/account/trades"
MY_TRADES_PATH_URL = "/api/v1/account/trades"
FUNDING_PAYMENTS_URL = "/api/v1/account/funding-payments"

# Transaction endpoints
NEXT_NONCE_URL = "/api/v1/transaction/next-nonce"
SEND_TX_URL = "/api/v1/transaction/send"
SEND_TX_BATCH_URL = "/api/v1/transaction/send-batch"

# WebSocket channels
TRADES_ENDPOINT_NAME = "trades"
DEPTH_ENDPOINT_NAME = "orderbook"
USER_ORDERS_ENDPOINT_NAME = "account-updates"
USEREVENT_ENDPOINT_NAME = "account-updates"
MARK_PRICE_CHANNEL = "mark-price"
FUNDING_RATE_CHANNEL = "funding-rates"

DIFF_EVENT_TYPE = "orderbook"
TRADE_EVENT_TYPE = "trades"

# Order Statuses - Lighter format
ORDER_STATE = {
    "pending": OrderState.PENDING_CREATE,
    "open": OrderState.OPEN,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "filled": OrderState.FILLED,
    "cancelled": OrderState.CANCELED,
    "canceled": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
    "expired": OrderState.CANCELED,
    "failed": OrderState.FAILED,
}

# Order Types - Lighter format
ORDER_TYPE_LIMIT = "LIMIT"
ORDER_TYPE_MARKET = "MARKET"
ORDER_TYPE_STOP_LOSS = "STOP_LOSS"
ORDER_TYPE_STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
ORDER_TYPE_TAKE_PROFIT = "TAKE_PROFIT"
ORDER_TYPE_TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"
ORDER_TYPE_TWAP = "TWAP"

# Time in Force - Lighter format
ORDER_TIME_IN_FORCE_IOC = "IMMEDIATE_OR_CANCEL"
ORDER_TIME_IN_FORCE_GTC = "GOOD_TILL_TIME"
ORDER_TIME_IN_FORCE_POST_ONLY = "POST_ONLY"

HEARTBEAT_TIME_INTERVAL = 30.0

MAX_REQUEST = 1_200
ALL_ENDPOINTS_LIMIT = "All"

RATE_LIMITS = [
    RateLimit(limit_id=ALL_ENDPOINTS_LIMIT, limit=100, time_interval=1),
    
    # Public endpoints
    RateLimit(
        limit_id=EXCHANGE_INFO_URL,
        limit=100,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=TICKER_PRICE_CHANGE_URL,
        limit=100,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=SNAPSHOT_REST_URL,
        limit=100,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=FUNDING_RATES_URL,
        limit=100,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=RECENT_TRADES_URL,
        limit=100,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    
    # Private endpoints
    RateLimit(
        limit_id=ACCOUNT_INFO_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=BALANCE_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=POSITIONS_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=CREATE_ORDER_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=CANCEL_ORDER_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=MY_TRADES_PATH_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=NEXT_NONCE_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
    RateLimit(
        limit_id=SEND_TX_URL,
        limit=50,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)],
    ),
]

