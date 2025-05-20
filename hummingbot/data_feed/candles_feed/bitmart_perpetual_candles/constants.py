from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://api-cloud-v2.bitmart.com"
HEALTH_CHECK_ENDPOINT = "/system/time"
CANDLES_ENDPOINT = "/contract/public/kline"
CONTRACT_INFO_URL = "/contract/public/details?symbol={contract}"

WSS_URL = "wss://openapi-ws-v2.bitmart.com"

INTERVALS = bidict({
    "1m": 1,
    # "3m": 3,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "2h": 120,
    "4h": 240,
    # "6h": 360,
    "12h": 720,
    "1d": 1440,
    # "3d": 4320,
    "1w": 10080,
})

MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 1000

RATE_LIMITS = [
    RateLimit(CANDLES_ENDPOINT, limit=12, time_interval=2, linked_limits=[LinkedLimitWeightPair("raw", 1)]),
    RateLimit(CONTRACT_INFO_URL, limit=12, time_interval=2, linked_limits=[LinkedLimitWeightPair("raw", 1)]),
    RateLimit(HEALTH_CHECK_ENDPOINT, limit=10, time_interval=1, linked_limits=[LinkedLimitWeightPair("raw", 1)])]
