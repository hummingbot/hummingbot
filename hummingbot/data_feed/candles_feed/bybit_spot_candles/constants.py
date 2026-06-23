from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://api.bybit.com"
HEALTH_CHECK_ENDPOINT = "/v5/market/time"
CANDLES_ENDPOINT = "/v5/market/kline"

WSS_URL = "wss://stream.bybit.com/v5/public/spot"

INTERVALS = bidict({
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "2h": 120,
    "4h": 240,
    "6h": 360,
    "12h": 720,
    "1d": "D",
    "1w": "W",
    "1M": "M"
})

MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 1000

# Shared GET/POST pool of the bybit spot connector (bybit_constants.REQUEST_GET_POST_SHARED).
# Matching this limit_id lets the candle feed consume from the connector's pool when they share a throttler.
REQUEST_GET_POST_SHARED = "ALL"
SHARED_RATE_LIMIT = 600  # per 5 seconds

RATE_LIMITS = [
    RateLimit(REQUEST_GET_POST_SHARED, limit=SHARED_RATE_LIMIT, time_interval=5),
    RateLimit(CANDLES_ENDPOINT, limit=20000, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(REQUEST_GET_POST_SHARED, 1)]),
    RateLimit(HEALTH_CHECK_ENDPOINT, limit=20000, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(REQUEST_GET_POST_SHARED, 1)])]
