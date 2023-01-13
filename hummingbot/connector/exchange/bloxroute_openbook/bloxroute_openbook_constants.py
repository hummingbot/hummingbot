from bxsolana.provider import constants
from bxsolana_trader_proto import Project

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

TOKEN_PAIR_TO_WALLET_ADDR = {
    "INV": "8U7VYzRnwLgKMXtp5bweXoDrzmQ1rF48a8qoD3rrc3uU",
    "SOL": "BZYcWxuhyZqWYbo6UPEEnYzrXGCe7tjcRQvZzz7cxqhq",
    "USDC": "HmvqBfBSRjNzjzKmjvefBe9NX9y2oSyiFLn77DwaH6v9",
    "mSOL": "SX4fHc9uL9x8VU6Ag2X8GR22bXPTwDjAcWFu7BfH2qg",
    "FIDA": "4aDUpyixMgbPzVcNdgxnw94chyoeMHe35W3dPCtXoY37",
    "RAY": "4aDUpyixMgbPzVcNdgxnw94chyoeMHe35W3dPCtXoY37",
    "WETH": "F2djfvy9ujH9mS4yf8zfHh1WHhGzNYJLxEKhEFbULgDv"
}

EXCHANGE_NAME = "bloxroute_openbook"
OPENBOOK_PROJECT = Project.P_OPENBOOK

REST_URL = "https://virginia.solana.dex.blxrbdn.com"
WSS_PUBLIC_URL = "wss://virginia.solana.dex.blxrbdn.com/ws"
WSS_PRIVATE_URL = "wss://virginia.solana.dex.blxrbdn.com/ws"
WS_PING_TIMEOUT = 20 * 0.8

DEFAULT_DOMAIN = ""
MAX_ORDER_ID_LEN = 32
HBOT_ORDER_ID_PREFIX = ""
BROKER_ID = "hummingbotfound"

# Base URL
WSS_URL = constants.MAINNET_API_WS

# WS API ENDPOINTS
WS_CONNECT = "WSConnect"
WS_SUBSCRIBE = "WSSubscribe"

SERVER_TIME_PATH = "/api/v1/system/time"
MARKET_PATH = "/api/v1/market/markets"

# Private API endpoints or BinanceClient function
ACCOUNTS_PATH_URL = "/account"
MY_TRADES_PATH_URL = "/myTrades"
ORDER_PATH_URL = "/order"
BINANCE_USER_STREAM_PATH_URL = "/userDataStream"

WS_HEARTBEAT_TIME_INTERVAL = 30

# Binance params

SIDE_BUY = 'BUY'
SIDE_SELL = 'SELL'

TIME_IN_FORCE_GTC = 'GTC'  # Good till cancelled
TIME_IN_FORCE_IOC = 'IOC'  # Immediate or cancel
TIME_IN_FORCE_FOK = 'FOK'  # Fill or kill

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS = "ORDERS"
ORDERS_24HR = "ORDERS_24HR"
RAW_REQUESTS = "RAW_REQUESTS"

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 5000

# Order States
ORDER_STATE = {
    "PENDING": OrderState.PENDING_CREATE,
    "NEW": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "PENDING_CANCEL": OrderState.OPEN,
    "CANCELED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.FAILED,
}

# Websocket event types

RATE_LIMITS = [
    # Pools
    # RateLimit(limit_id=REQUEST_WEIGHT, limit=1200, time_interval=ONE_MINUTE),
    # RateLimit(limit_id=ORDERS, limit=50, time_interval=10 * ONE_SECOND),
    # RateLimit(limit_id=ORDERS_24HR, limit=160000, time_interval=ONE_DAY),
    # RateLimit(limit_id=RAW_REQUESTS, limit=6100, time_interval= 5 * ONE_MINUTE),
    # # Weighted Limits
    # RateLimit(limit_id=TICKER_PRICE_CHANGE_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 40),
    #                          LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    # RateLimit(limit_id=TICKER_BOOK_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 2),
    #                          LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    # RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10),
    #                          LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    # RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 50),
    #                          LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    # RateLimit(limit_id=BINANCE_USER_STREAM_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
    #                          LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    # RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
    #                          LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    # RateLimit(limit_id=PING_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
    #                          LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    # RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10),
    #                          LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    # RateLimit(limit_id=MY_TRADES_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10),
    #                          LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    # RateLimit(limit_id=ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 2),
    #                          LinkedLimitWeightPair(ORDERS, 1),
    #                          LinkedLimitWeightPair(ORDERS_24HR, 1),
    #                          LinkedLimitWeightPair(RAW_REQUESTS, 1)])
]
