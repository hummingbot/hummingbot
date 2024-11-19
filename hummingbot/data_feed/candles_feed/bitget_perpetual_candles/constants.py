from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

#https://api.bitget.com/api/v2/mix/market/candles?symbol=BTCUSDT&granularity=5m&limit=100&productType=usdt-futures
REST_URL = "https://api.bitget.com"
HEALTH_CHECK_ENDPOINT = "/api/spot/v1/public/time"
CANDLES_ENDPOINT = "/api/v2/mix/market/history-candles"

WSS_URL = "wss://ws.bitget.com/mix/v1/stream"

INTERVALS = bidict({
    "1s": 1,
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    #"1H"
    "1h": 3600,
    #"4H"
    "4h": 14400,
    #"6H"
    "6h": 21600,
    #"12H"
    "12h": 43200,
    #"1D"
    "1d": 86400,
    #"1W"
    "1w": 604800,
    "1M": 2592000
})
MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 100
REQUEST_WEIGHT = "REQUEST_WEIGHT"

RATE_LIMITS = [
    RateLimit(REQUEST_WEIGHT, limit=100, time_interval=60),
    RateLimit(CANDLES_ENDPOINT, weight=2, limit=100, time_interval=60, linked_limits=[LinkedLimitWeightPair("raw", 1)]),
    RateLimit(HEALTH_CHECK_ENDPOINT, limit=100, time_interval=60, linked_limits=[LinkedLimitWeightPair("raw", 1)])]
