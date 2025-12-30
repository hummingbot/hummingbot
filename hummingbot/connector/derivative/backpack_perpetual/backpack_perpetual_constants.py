from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "backpack_perpetual"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = 36  # UUID format

MARKET_ORDER_SLIPPAGE = 0.05

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "backpack_perpetual_testnet"

# REST API URLs
BASE_URL = "https://api.backpack.exchange"
TESTNET_BASE_URL = "https://api.backpack.exchange"  # Backpack uses same URL, different API keys

# WebSocket URLs
WS_URL = "wss://ws.backpack.exchange"
TESTNET_WS_URL = "wss://ws.backpack.exchange"

# Authentication
DEFAULT_WINDOW = 5000  # 5 seconds validity window
MAX_WINDOW = 60000  # 60 seconds max

# Funding rate update interval
FUNDING_RATE_UPDATE_INTERVAL_SECONDS = 60

# Currency
CURRENCY = "USDC"

# REST Endpoints - Public
MARKETS_URL = "/api/v1/markets"
TICKER_URL = "/api/v1/ticker"
TICKERS_URL = "/api/v1/tickers"
DEPTH_URL = "/api/v1/depth"
TRADES_URL = "/api/v1/trades"
KLINES_URL = "/api/v1/klines"
STATUS_URL = "/api/v1/status"
PING_URL = "/api/v1/ping"
TIME_URL = "/api/v1/time"
ASSETS_URL = "/api/v1/assets"
FUNDING_RATES_URL = "/api/v1/fundingRates"
MARK_PRICES_URL = "/api/v1/markPrices"

# REST Endpoints - Private (require auth)
CAPITAL_URL = "/api/v1/capital"
BALANCE_URL = "/api/v1/capital"
ORDER_URL = "/api/v1/order"
ORDERS_URL = "/api/v1/orders"
ACCOUNT_URL = "/api/v1/account"
FILLS_URL = "/api/v1/fills"
POSITION_URL = "/api/v1/position"
POSITIONS_URL = "/api/v1/positions"
LEVERAGE_URL = "/api/v1/leverage"

# Instruction types for signing
INSTRUCTION_BALANCE_QUERY = "balanceQuery"
INSTRUCTION_ORDER_EXECUTE = "orderExecute"
INSTRUCTION_ORDER_CANCEL = "orderCancel"
INSTRUCTION_ORDER_QUERY = "orderQuery"
INSTRUCTION_ORDER_QUERY_ALL = "orderQueryAll"
INSTRUCTION_ORDER_CANCEL_ALL = "orderCancelAll"
INSTRUCTION_ACCOUNT_QUERY = "accountQuery"
INSTRUCTION_POSITION_QUERY = "positionQuery"
INSTRUCTION_LEVERAGE_UPDATE = "leverageUpdate"

# WebSocket Channels - Public
WS_DEPTH_CHANNEL = "depth"
WS_TRADE_CHANNEL = "trade"
WS_TICKER_CHANNEL = "ticker"
WS_BOOK_TICKER_CHANNEL = "bookTicker"
WS_MARK_PRICE_CHANNEL = "markPrice"
WS_FUNDING_RATE_CHANNEL = "fundingRate"

# WebSocket Channels - Private
WS_ORDER_UPDATE_CHANNEL = "account.orderUpdate"
WS_POSITION_UPDATE_CHANNEL = "account.positionUpdate"
WS_FILL_CHANNEL = "account.fill"

# WebSocket Event Types
DIFF_EVENT_TYPE = "depth"
TRADE_EVENT_TYPE = "trade"
ORDER_UPDATE_EVENT_TYPE = "orderUpdate"
POSITION_UPDATE_EVENT_TYPE = "positionUpdate"

# Order Statuses - Backpack uses these status strings
ORDER_STATE = {
    "New": OrderState.OPEN,
    "PartiallyFilled": OrderState.PARTIALLY_FILLED,
    "Filled": OrderState.FILLED,
    "Cancelled": OrderState.CANCELED,
    "Canceled": OrderState.CANCELED,  # Handle both spellings
    "Expired": OrderState.CANCELED,
    "Rejected": OrderState.FAILED,
}

# Order Types
ORDER_TYPE_LIMIT = "Limit"
ORDER_TYPE_MARKET = "Market"

# Order Sides
ORDER_SIDE_BID = "Bid"
ORDER_SIDE_ASK = "Ask"

# Position Sides
POSITION_SIDE_LONG = "Long"
POSITION_SIDE_SHORT = "Short"

# Time in Force
TIF_GTC = "GTC"  # Good Till Cancel
TIF_IOC = "IOC"  # Immediate Or Cancel
TIF_FOK = "FOK"  # Fill Or Kill

# Self Trade Prevention
STP_REJECT_TAKER = "RejectTaker"
STP_REJECT_MAKER = "RejectMaker"
STP_REJECT_BOTH = "RejectBoth"

HEARTBEAT_TIME_INTERVAL = 30.0

# Rate Limits - Using conservative defaults
MAX_REQUEST = 1200  # requests per minute
ALL_ENDPOINTS_LIMIT = "All"

# Error Messages
ORDER_NOT_EXIST_MESSAGE = "Order not found"
UNKNOWN_ORDER_MESSAGE = "Order does not exist"

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=MAX_REQUEST, time_interval=60),

    # Public endpoints
    RateLimit(limit_id=MARKETS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=TICKER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=TICKERS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=DEPTH_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=TRADES_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=PING_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=TIME_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=STATUS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=FUNDING_RATES_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=MARK_PRICES_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),

    # Private endpoints
    RateLimit(limit_id=CAPITAL_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ORDERS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ACCOUNT_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=FILLS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=POSITION_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=POSITIONS_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=LEVERAGE_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
]
