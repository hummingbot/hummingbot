from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://api.bitget.com"
WSS_URL = "wss://ws.bitget.com/v2/ws/public"

HEALTH_CHECK_ENDPOINT = "/api/v2/public/time"
CANDLES_ENDPOINT = "/api/v2/spot/market/candles"
WS_CANDLES_ENDPOINT = "candle"
PUBLIC_WS_PING_REQUEST = "ping"

WS_HEARTBEAT_TIME_INTERVAL = 30

MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 1000

INTERVAL_LIMITS_DAYS = {
    "1m": 30,
    "3m": 30,
    "5m": 30,
    "15m": 52,
    "30m": 62,
    "1h": 83,
    "2h": 120,
    "4h": 240,
    "6h": 360
}

INTERVALS = bidict({
    "1m": "1min",
    "3m": "3min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "4h": "4h",
    "6h": "6h",
    "12h": "12h",
    "1d": "1day",
    "3d": "3day",
    "1w": "1week",
    "1M": "1M"
})

WS_INTERVALS = bidict({
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1H",
    "4h": "4H",
    "6h": "6H",
    "12h": "12H",
    "1d": "1D",
    "3d": "3D",
    "1w": "1W",
    "1M": "1M"
})

RATE_LIMITS = [
    RateLimit(CANDLES_ENDPOINT, limit=20, time_interval=1, linked_limits=[LinkedLimitWeightPair("raw", 1)]),
    RateLimit(HEALTH_CHECK_ENDPOINT, limit=10, time_interval=1, linked_limits=[LinkedLimitWeightPair("raw", 1)])
]
