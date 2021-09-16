from hummingbot.core.api_throttler.data_types import RateLimit, LinkedLimitWeightPair

KRAKEN_TO_HB_MAP = {
    "XBT": "BTC",
    "XDG": "DOGE",
}

BASE_URL = "https://api.kraken.com"
TICKER_PATH_URL = "/0/public/Ticker"
SNAPSHOT_PATH_URL = "/0/public/Depth"
ASSET_PAIRS_PATH_URL = "/0/public/AssetPairs"
TIME_PATH_URL = "/0/public/Time"
GET_TOKEN_PATH_URL = "/0/private/GetWebSocketsToken"
ADD_ORDER_PATH_URL = "/0/private/AddOrder"
CANCEL_ORDER_PATH_URL = "/0/private/CancelOrder"
BALANCE_PATH_URL = "/0/private/Balance"
OPEN_ORDERS_PATH_URL = "/0/private/OpenOrders"
QUERY_ORDERS_PATH_URL = "/0/private/QueryOrders"

WS_URL = "wss://ws.kraken.com"
WS_AUTH_URL = "wss://ws-auth.kraken.com/"

PUBLIC_ENDPOINT_LIMIT_ID = "PublicEndpointLimitID"
PUBLIC_ENDPOINT_LIMIT = 1
PUBLIC_ENDPOINT_LIMIT_INTERVAL = 1
PRIVATE_ENDPOINT_LIMIT_ID = "PrivateEndpointLimitID"
PRIVATE_ENDPOINT_LIMIT = 15 + 20  # relaxed for limit-decay; one extra call every 3s; issue #4178 for details
PRIVATE_ENDPOINT_LIMIT_INTERVAL = 60
MATCHING_ENGINE_LIMIT_ID = "MatchingEngineLimitID"
MATCHING_ENGINE_LIMIT = 60 + 60    # relaxed for limit-decay; one extra call every 1s; issue #4178 for details
MATCHING_ENGINE_LIMIT_INTERVAL = 60
WS_CONNECTION_LIMIT_ID = "WSConnectionLimitID"

RATE_LIMITS = [
    RateLimit(
        limit_id=PUBLIC_ENDPOINT_LIMIT_ID,
        limit=PUBLIC_ENDPOINT_LIMIT,
        time_interval=PUBLIC_ENDPOINT_LIMIT_INTERVAL,
    ),
    RateLimit(
        limit_id=PRIVATE_ENDPOINT_LIMIT_ID,
        limit=PRIVATE_ENDPOINT_LIMIT,
        time_interval=PRIVATE_ENDPOINT_LIMIT_INTERVAL,
    ),
    RateLimit(
        limit_id=MATCHING_ENGINE_LIMIT_ID,
        limit=MATCHING_ENGINE_LIMIT,
        time_interval=MATCHING_ENGINE_LIMIT_INTERVAL,
    ),
    # public endpoints
    RateLimit(
        limit_id=SNAPSHOT_PATH_URL,
        limit=PUBLIC_ENDPOINT_LIMIT,
        time_interval=PUBLIC_ENDPOINT_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_ENDPOINT_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=ASSET_PAIRS_PATH_URL,
        limit=PUBLIC_ENDPOINT_LIMIT,
        time_interval=PUBLIC_ENDPOINT_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_ENDPOINT_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=TICKER_PATH_URL,
        limit=PUBLIC_ENDPOINT_LIMIT,
        time_interval=PUBLIC_ENDPOINT_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_ENDPOINT_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=TIME_PATH_URL,
        limit=PUBLIC_ENDPOINT_LIMIT,
        time_interval=PUBLIC_ENDPOINT_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_ENDPOINT_LIMIT_ID)],
    ),
    # private endpoints
    RateLimit(
        limit_id=GET_TOKEN_PATH_URL,
        limit=PRIVATE_ENDPOINT_LIMIT,
        time_interval=PRIVATE_ENDPOINT_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_ENDPOINT_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=BALANCE_PATH_URL,
        limit=PRIVATE_ENDPOINT_LIMIT,
        time_interval=PRIVATE_ENDPOINT_LIMIT_INTERVAL,
        weight=2,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_ENDPOINT_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=OPEN_ORDERS_PATH_URL,
        limit=PRIVATE_ENDPOINT_LIMIT,
        time_interval=PRIVATE_ENDPOINT_LIMIT_INTERVAL,
        weight=2,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_ENDPOINT_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=QUERY_ORDERS_PATH_URL,
        limit=PRIVATE_ENDPOINT_LIMIT,
        time_interval=PRIVATE_ENDPOINT_LIMIT_INTERVAL,
        weight=2,
        linked_limits=[LinkedLimitWeightPair(PRIVATE_ENDPOINT_LIMIT_ID)],
    ),
    # matching engine endpoints
    RateLimit(
        limit_id=ADD_ORDER_PATH_URL,
        limit=MATCHING_ENGINE_LIMIT,
        time_interval=MATCHING_ENGINE_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(MATCHING_ENGINE_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=CANCEL_ORDER_PATH_URL,
        limit=MATCHING_ENGINE_LIMIT,
        time_interval=MATCHING_ENGINE_LIMIT_INTERVAL,
        linked_limits=[LinkedLimitWeightPair(MATCHING_ENGINE_LIMIT_ID)],
    ),
    # ws connections limit
    RateLimit(limit_id=WS_CONNECTION_LIMIT_ID, limit=150, time_interval=60 * 10),
]
