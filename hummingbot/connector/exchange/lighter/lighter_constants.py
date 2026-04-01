from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

EXCHANGE_NAME = "lighter"
DEFAULT_DOMAIN = "lighter"
HBOT_ORDER_ID_PREFIX = "HBOT"
MAX_ORDER_ID_LEN = 32

REST_URL = "https://mainnet.zklighter.elliot.ai/api/v1"
WSS_URL = "wss://mainnet.zklighter.elliot.ai/stream"

TESTNET_DOMAIN = "lighter_testnet"
TESTNET_REST_URL = "https://testnet.zklighter.elliot.ai/api/v1"
TESTNET_WSS_URL = "wss://testnet.zklighter.elliot.ai/stream"

PING_PATH_URL = "/orderBooks"
EXCHANGE_INFO_PATH_URL = "/orderBooks"
GET_MARKET_ORDER_BOOK_SNAPSHOT_PATH_URL = "/orderbooks"
GET_ORDER_HISTORY_PATH_URL = "/accountInactiveOrders"
GET_TRADE_HISTORY_PATH_URL = "/trades"
GET_ACCOUNT_INFO_PATH_URL = "/account"
GET_ACCOUNT_API_CONFIG_KEYS = "/apikeys"
CREATE_ACCOUNT_API_CONFIG_KEY = "/tokens_create"
CREATE_ORDER_PATH_URL = "/sendTx"
CANCEL_ORDER_PATH_URL = "/sendTx"

WS_ORDER_BOOK_SNAPSHOT_CHANNEL = "order_book"
WS_TRADES_CHANNEL = "trade"
WS_ACCOUNT_ALL_CHANNEL = "account_all"
WS_PING_INTERVAL = 30

LIGHTER_LIMIT_ID = "LIGHTER_LIMIT"
LIGHTER_LIMIT = 24000
LIGHTER_LIMIT_INTERVAL = 60
STANDARD_REQUEST_COST = 10
HEAVY_GET_REQUEST_COST = 30
ORDER_CANCELLATION_COST = 5

RATE_LIMITS = [
    RateLimit(limit_id=LIGHTER_LIMIT_ID, limit=LIGHTER_LIMIT, time_interval=LIGHTER_LIMIT_INTERVAL),
    RateLimit(
        limit_id=EXCHANGE_INFO_PATH_URL,
        limit=LIGHTER_LIMIT,
        time_interval=LIGHTER_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST)],
    ),
    RateLimit(
        limit_id=GET_MARKET_ORDER_BOOK_SNAPSHOT_PATH_URL,
        limit=LIGHTER_LIMIT,
        time_interval=LIGHTER_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST)],
    ),
    RateLimit(
        limit_id=GET_ACCOUNT_INFO_PATH_URL,
        limit=LIGHTER_LIMIT,
        time_interval=LIGHTER_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST)],
    ),
    RateLimit(
        limit_id=GET_TRADE_HISTORY_PATH_URL,
        limit=LIGHTER_LIMIT,
        time_interval=LIGHTER_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST)],
    ),
    RateLimit(
        limit_id=GET_ORDER_HISTORY_PATH_URL,
        limit=LIGHTER_LIMIT,
        time_interval=LIGHTER_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST)],
    ),
    RateLimit(
        limit_id=CREATE_ORDER_PATH_URL,
        limit=LIGHTER_LIMIT,
        time_interval=LIGHTER_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=STANDARD_REQUEST_COST)],
    ),
    RateLimit(
        limit_id=CANCEL_ORDER_PATH_URL,
        limit=LIGHTER_LIMIT,
        time_interval=LIGHTER_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(limit_id=LIGHTER_LIMIT_ID, weight=ORDER_CANCELLATION_COST)],
    ),
]
