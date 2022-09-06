from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "com.br"

HBOT_ORDER_ID_PREFIX = "55"
USER_AGENT = "HBOT"
MAX_ORDER_ID_LEN = 20

# Base URL
# REST_URL = "api.foxbit.com.br"
# WSS_URL = "api.foxbit.com.br"
REST_URL = "api-homolog.thesail.pro"
WSS_URL = "foxbit-api-gateway-homolog.thesail.pro"

PUBLIC_API_VERSION = "v3"
PRIVATE_API_VERSION = "v3"

# Public API endpoints or FoxbitClient function
TICKER_PRICE_CHANGE_PATH_URL = "SubscribeLevel1"
EXCHANGE_INFO_PATH_URL = "markets"
PING_PATH_URL = "system/time"
SNAPSHOT_PATH_URL = "markets/{}/orderbook"
SERVER_TIME_PATH_URL = "system/time"

# Private API endpoints or FoxbitClient function
ACCOUNTS_PATH_URL = "accounts"
MY_TRADES_PATH_URL = "trades"
ORDER_PATH_URL = "orders"
CANCEL_ORDER_PATH_URL = "orders/cancel"
GET_ORDER_BY_ID = "orders/by-order-id/{}"

WS_HEADER = {
    "Content-Type": "application/json",
    "User-Agent": USER_AGENT,
}

WS_MESSAGE_FRAME_TYPE = {
    "Request": 0,
    "Reply": 1,
    "Subscribe": 2,
    "Event": 3,
    "Unsubscribe": 4,
}

WS_MESSAGE_FRAME = {
    "m": 0,                 # WS_MESSAGE_FRAME_TYPE
    "i": 0,                 # Sequence Number
    "n": "",                # Endpoint
    "o": "",                # Message Payload
}

WS_CHANNELS = {
    "USER_STREAM": [
        "balance:all",
        "position:all",
        "order:all",
    ]
}

WS_HEARTBEAT_TIME_INTERVAL = 20

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

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 100

# Order States
ORDER_STATE = {
    "PENDING": OrderState.PENDING_CREATE,
    "ACTIVE": OrderState.OPEN,
    "NEW": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "PENDING_CANCEL": OrderState.OPEN,
    "CANCELED": OrderState.CANCELED,
    "PARTIALLY_CANCELED": OrderState.PARTIALLY_FILLED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.FAILED,
}

# Websocket subscribe endpoint
WS_SUBSCRIBE_ACCOUNT = "SubscribeAccountEvents"
WS_SUBSCRIBE_ORDER_BOOK = "SubscribeLevel2"
WS_SUBSCRIBE_TOB = "SubscribeLevel1"
WS_SUBSCRIBE_TRADES = "SubscribeTrades"

# Websocket response event types from Foxbit
WS_ORDER_BOOK_RESPONSE = "Level2UpdateEvent"
WS_TRADE_RESPONSE = "TradeDataUpdateEvent"
WS_ORDER_STATE = "OrderStateEvent"
WS_TRADE_STATE = "OrderTradeEvent"

ORDER_BOOK_DEPTH = 5

RATE_LIMITS = [
    # Pools
    RateLimit(limit_id=REQUEST_WEIGHT, limit=1200, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=ORDERS_24HR, limit=100000, time_interval=ONE_DAY),
    # Weighted Limits
    RateLimit(limit_id=TICKER_PRICE_CHANGE_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 40)]),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[(LinkedLimitWeightPair(REQUEST_WEIGHT, 10))]),
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 50)]),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=PING_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10)]),
    RateLimit(limit_id=MY_TRADES_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10)]),
    RateLimit(limit_id=GET_ORDER_BY_ID, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10)]),
    RateLimit(limit_id=CANCEL_ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10)]),
    RateLimit(limit_id=ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(ORDERS, 1),
                             LinkedLimitWeightPair(ORDERS_24HR, 1)]),
]
