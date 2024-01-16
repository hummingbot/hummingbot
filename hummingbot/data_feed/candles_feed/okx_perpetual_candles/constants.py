from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

# Update REST, WS and HEALTH endpoints with https://www.okx.com/docs-v5/en/?shell#overview-account-mode
REST_URL = "https://www.okx.com"
HEALTH_CHECK_ENDPOINT = "/api/v5/system/status"
CANDLES_ENDPOINT = "/api/v5/market/history-candles"
WSS_URL = "wss://ws.okx.com:8443/ws/v5/business"

# Update bidict intervals with https://www.okx.com/docs-v5/en/?shell#order-book-trading-market-data-get-candlesticks-history
INTERVALS = bidict({
    "1s": "1s",
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1H",
    "2h": "2H",
    "4h": "4H",
    "6h": "6Hutc",
    "8h": "8Hutc",
    "12h": "12Hutc",
    "1d": "1Dutc",
    "3d": "3Dutc",
    "1w": "1Wutc",
    "1M": "1Mutc",
    "3M": "3Mutc"
})

# TODO: What is request_weight
REQUEST_WEIGHT = "REQUEST_WEIGHT"

MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 100
# Update rate limits according to every endpoint
RATE_LIMITS = [
    RateLimit(REQUEST_WEIGHT, limit=6000, time_interval=60),
    RateLimit(CANDLES_ENDPOINT, limit=40, time_interval=2, linked_limits=[LinkedLimitWeightPair("raw", 1)]),
    RateLimit(HEALTH_CHECK_ENDPOINT, limit=1200, time_interval=60, linked_limits=[LinkedLimitWeightPair("raw", 1)])]
