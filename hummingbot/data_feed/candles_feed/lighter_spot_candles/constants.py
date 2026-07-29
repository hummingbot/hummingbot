from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

MAINNET_BASE_URL = "https://mainnet.zklighter.elliot.ai"
MAINNET_WS_URL = "wss://mainnet.zklighter.elliot.ai/stream"

CANDLES_PATH_URL = "/api/v1/candles"
ORDER_BOOK_DETAILS_PATH_URL = "/api/v1/orderBookDetails"
EXCHANGE_STATS_PATH_URL = "/api/v1/exchangeStats"

MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 1000
CANDLE_POLL_INTERVAL_SECONDS = 10.0

INTERVALS = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "12h": "12h",
    "1d": "1d",
    "1w": "1w",
}

# Rate limits — https://apidocs.lighter.xyz/docs/rate-limits
# Lighter throttles against a weighted request pool per rolling minute. Every endpoint this
# read-only candles feed uses (candles, orderBookDetails, exchangeStats) is an "Other endpoint"
# with weight 300. A standard account is capped at 60 requests/minute, so the shared pool is
# sized at 60 * 300 = 18,000 weighted points; each weight-300 call costs 300, giving the
# equivalent of 60 calls/minute.
# Shared weighted pool of the lighter connector (lighter_constants.ALL_ENDPOINTS_LIMIT).
# Matching this limit_id lets the candle feed consume from the connector's pool when they share a throttler.
ALL_ENDPOINTS_LIMIT = "lighter_all"
WEIGHT_DEFAULT = 300
STANDARD_ACCOUNT_REQUEST_LIMIT = 60
ALL_ENDPOINTS_POOL = STANDARD_ACCOUNT_REQUEST_LIMIT * WEIGHT_DEFAULT  # 18,000

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=ALL_ENDPOINTS_POOL, time_interval=60),
    RateLimit(
        CANDLES_PATH_URL,
        limit=WEIGHT_DEFAULT,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_DEFAULT)],
    ),
    RateLimit(
        ORDER_BOOK_DETAILS_PATH_URL,
        limit=WEIGHT_DEFAULT,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_DEFAULT)],
    ),
    RateLimit(
        EXCHANGE_STATS_PATH_URL,
        limit=WEIGHT_DEFAULT,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_DEFAULT)],
    ),
]
