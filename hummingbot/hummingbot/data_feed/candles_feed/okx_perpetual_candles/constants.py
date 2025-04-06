from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://www.okx.com"
WSS_URL = "wss://ws.okx.com:8443/ws/v5/business"

# GET / Candlesticks history (https://www.okx.com/docs-v5/en/?shell#order-book-trading-market-data-get-candlesticks-history)
# Retrieve history candlestick charts from recent years(It is last 3 months supported for 1s candlestick).
# Rate Limit: 20 requests per 2 seconds
# Rate limit rule: IP
CANDLES_ENDPOINT = "/api/v5/market/history-candles"
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
MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 100

# Get system time (https://www.okx.com/docs-v5/en/?shell#public-data-rest-api-get-system-time)
# Retrieve API server time.
# Rate Limit: 10 requests per 2 seconds
# Rate limit rule: IP
HEALTH_CHECK_ENDPOINT = "/api/v5/public/time"

RATE_LIMITS = [
    RateLimit(CANDLES_ENDPOINT, limit=20, time_interval=2, linked_limits=[LinkedLimitWeightPair("raw", 1)]),
    RateLimit(HEALTH_CHECK_ENDPOINT, limit=10, time_interval=2, linked_limits=[LinkedLimitWeightPair("raw", 1)])]
