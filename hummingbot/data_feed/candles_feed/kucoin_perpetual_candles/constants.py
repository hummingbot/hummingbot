import sys

from bidict import bidict

from hummingbot.core.api_throttler.data_types import RateLimit

REST_URL = "https://api-futures.kucoin.com"
HEALTH_CHECK_ENDPOINT = "/api/v1/timestamp"
CANDLES_ENDPOINT = "/api/v1/kline/query"
SYMBOLS_ENDPOINT = "/api/v1/contracts/active"

HB_TO_KUCOIN_MAP = {
    "BTC": "XBT",
}

PUBLIC_WS_DATA_PATH_URL = "/api/v1/bullet-public"

KLINE_PUSH_WEB_SOCKET_TOPIC = "/contractMarket/limitCandle"

INTERVALS = bidict({
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
    "1M": "1month",
})

GRANULARITIES = bidict({
    "1m": 1,
    "3m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "2h": 120,
    "4h": 240,
    "6h": 480,
    "8h": 720,
    "12h": 1440,
    "1d": 10080,
})
MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 500
REQUEST_WEIGHT = "REQUEST_WEIGHT"
NO_LIMIT = sys.maxsize


RATE_LIMITS = [
    RateLimit(limit_id=PUBLIC_WS_DATA_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(CANDLES_ENDPOINT, limit=30, time_interval=60),
    RateLimit(HEALTH_CHECK_ENDPOINT, limit=30, time_interval=60),
    RateLimit(SYMBOLS_ENDPOINT, limit=30, time_interval=60),]
