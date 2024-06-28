import sys

from bidict import bidict

from hummingbot.core.api_throttler.data_types import RateLimit

REST_URL = "https://api.kucoin.com"
HEALTH_CHECK_ENDPOINT = "/api/v1/timestamp"
CANDLES_ENDPOINT = "/api/v1/market/candles"

PUBLIC_WS_DATA_PATH_URL = "/api/v1/bullet-public"

INTERVALS = bidict({
    "1m": "1min",
    "3m": "3min",
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
})
MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 1500

REQUEST_WEIGHT = "REQUEST_WEIGHT"
NO_LIMIT = sys.maxsize

RATE_LIMITS = [
    RateLimit(limit_id=PUBLIC_WS_DATA_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(CANDLES_ENDPOINT, limit=30, time_interval=60),
    RateLimit(HEALTH_CHECK_ENDPOINT, limit=30, time_interval=60)]
