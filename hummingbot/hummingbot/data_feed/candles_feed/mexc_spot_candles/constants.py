from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://api.mexc.com"
HEALTH_CHECK_ENDPOINT = "/api/v3/ping"
CANDLES_ENDPOINT = "/api/v3/klines"

WSS_URL = "wss://wbs.mexc.com/ws"

INTERVALS = bidict({
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "60m",
    "4h": "4h",
    "1d": "1d",
    "1w": "1W",
    "1M": "1M"
})

WS_INTERVALS = {
    "1m": "Min1",
    "5m": "Min5",
    "15m": "Min15",
    "30m": "Min30",
    "1h": "Min60",
    "4h": "Hour4",
    "8h": "Hour8",
    "1d": "Day1",
    "1w": "Week1",
    "1M": "Month1"
}

MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 1000

RATE_LIMITS = [
    RateLimit(CANDLES_ENDPOINT, limit=20000, time_interval=60, linked_limits=[LinkedLimitWeightPair("raw", 1)]),
    RateLimit(HEALTH_CHECK_ENDPOINT, limit=20000, time_interval=60, linked_limits=[LinkedLimitWeightPair("raw", 1)])]
