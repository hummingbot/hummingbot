from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://api.backpack.exchange"
HEALTH_CHECK_ENDPOINT = "/api/v1/status"
CANDLES_ENDPOINT = "/api/v1/klines"

WSS_URL = "wss://ws.backpack.exchange"

# Backpack uses "1month" instead of "1M" for the monthly interval. The bidict maps the
# Hummingbot-standard interval keys (left) to the Backpack-native interval values (right).
INTERVALS = bidict({
    "1s": "1s",
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "6h": "6h",
    "8h": "8h",
    "12h": "12h",
    "1d": "1d",
    "3d": "3d",
    "1w": "1w",
    "1M": "1month",
})

MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 1000
REQUEST_WEIGHT = "REQUEST_WEIGHT"

RATE_LIMITS = [
    RateLimit(REQUEST_WEIGHT, limit=6000, time_interval=60),
    RateLimit(CANDLES_ENDPOINT, limit=6000, time_interval=60, linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(HEALTH_CHECK_ENDPOINT, limit=6000, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
]
