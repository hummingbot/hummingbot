from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://api.kucoin.com"
HEALTH_CHECK_ENDPOINT = "/api/v1/timestamp"
CANDLES_ENDPOINT = "/api/v1/market/candles"

PUBLIC_WS_DATA_PATH_URL = "/api/v1/bullet-public"

INTERVALS = bidict({
    "1s": "1s",  # Implemented for resampling to 1s from trades in quants-lab
    "1m": "1min",
    "3m": "3min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1hour",
    "2h": "2hour",
    "4h": "4hour",
    "6h": "6hour",
    "8h": "8hour",
    "12h": "12hour",
    "1d": "1day",
    "1w": "1week",
    "1M": "1month"
})
MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 1500

MAX_REQUEST = 4000
TIME_INTERVAL = 30
REQUEST_WEIGHT = "REQUEST_WEIGHT"

RATE_LIMITS = [
    RateLimit(limit_id=REQUEST_WEIGHT, limit=MAX_REQUEST, time_interval=TIME_INTERVAL),
    RateLimit(limit_id=CANDLES_ENDPOINT, limit=MAX_REQUEST, time_interval=TIME_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=3)]),
    RateLimit(limit_id=HEALTH_CHECK_ENDPOINT, limit=MAX_REQUEST, time_interval=TIME_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=3)]),
    RateLimit(limit_id=PUBLIC_WS_DATA_PATH_URL, limit=MAX_REQUEST, time_interval=TIME_INTERVAL,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=10)]),
]
