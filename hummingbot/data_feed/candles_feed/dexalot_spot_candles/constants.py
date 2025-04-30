from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://api.dexalot.com/privapi"
HEALTH_CHECK_ENDPOINT = "/trading/environments"
CANDLES_ENDPOINT = "/trading/candlechart"

WSS_URL = "wss://api.dexalot.com/api/ws"

# "M5", "M15",  "M30",  "H1"  "H4",  "D1" only these are supported
INTERVALS = bidict({
    "5m": "M5",
    "15m": "M15",
    "30m": "M30",
    "1h": "H1",
    "4h": "H4",
    "1d": "D1",
})

MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 1000

RATE_LIMITS = [
    RateLimit(CANDLES_ENDPOINT, limit=20000, time_interval=60, linked_limits=[LinkedLimitWeightPair("raw", 1)]),
    RateLimit(HEALTH_CHECK_ENDPOINT, limit=20000, time_interval=60, linked_limits=[LinkedLimitWeightPair("raw", 1)])]
