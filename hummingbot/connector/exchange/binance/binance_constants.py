from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

# Base URL
REST_URL = "https://api.binance.{}/api/"
WSS_URL = "wss://stream.binance.{}:9443/ws"

PUBLIC_API_VERSION = "v1"
PRIVATE_API_VERSION = "v3"

# Public API endpoints or BinanceClient function
TICKER_PRICE_CHANGE_PATH_URL = "/ticker/24hr"
EXCHANGE_INFO_PATH_URL = "/exchangeInfo"
SNAPSHOT_PATH_URL = "/depth"
BINANCE_GET_EXCHANGE_INFO = "get_exchange_info"
BINANCE_GET_SERVER_TIME = "get_server_time"
BINANCE_PING = "ping"

# Private API endpoints or BinanceClient function
BINANCE_USER_STREAM_PATH_URL = "/userDataStream"
BINANCE_GET_ACCOUNT = "get_account"
BINANCE_GET_MY_TRADES = "get_my_trades"
BINANCE_GET_TRADE_FEE = "get_trade_fee"
BINANCE_GET_ORDER = "get_order"
BINANCE_CREATE_ORDER = "create_order"
BINANCE_CANCEL_ORDER = "cancel_order"
BINANCE_GET_OPEN_ORDERS = "get_open_orders"

WS_HEARTBEAT_TIME_INTERVAL = 30

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS = "ORDERS"
ORDERS_24HR = "ORDERS_24HR"

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 5000

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
    RateLimit(limit_id=BINANCE_USER_STREAM_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=BINANCE_GET_EXCHANGE_INFO, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10)]),
    RateLimit(limit_id=BINANCE_GET_SERVER_TIME, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=BINANCE_PING, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=BINANCE_GET_ACCOUNT, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10)]),
    RateLimit(limit_id=BINANCE_GET_MY_TRADES, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 10)]),
    RateLimit(limit_id=BINANCE_GET_TRADE_FEE, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=BINANCE_GET_ORDER, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 2)]),
    RateLimit(limit_id=BINANCE_CREATE_ORDER, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(ORDERS, 1),
                             LinkedLimitWeightPair(ORDERS_24HR, 1)]),
    RateLimit(limit_id=BINANCE_CANCEL_ORDER, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=BINANCE_GET_OPEN_ORDERS, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 40)]),
]
