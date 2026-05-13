from bidict import bidict

from hummingbot.core.api_throttler.data_types import RateLimit

REST_URL = "https://api.aevo.xyz"
WSS_URL = "wss://ws.aevo.xyz"

HEALTH_CHECK_ENDPOINT = "/time"
CANDLES_ENDPOINT = "/mark-history"

INTERVALS = bidict({
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "8h": 28800,
    "12h": 43200,
    "1d": 86400,
    "3d": 259200,
    "1w": 604800,
    "1M": 2592000,
})

MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 200

WS_TICKER_CHANNEL = "ticker-500ms"

RATE_LIMITS = [
    RateLimit(limit_id=CANDLES_ENDPOINT, limit=120, time_interval=60),
    RateLimit(limit_id=HEALTH_CHECK_ENDPOINT, limit=120, time_interval=60),
    RateLimit(limit_id=WSS_URL, limit=60, time_interval=60),
]

PING_TIMEOUT = 30.0
PING_PAYLOAD = {"op": "ping"}
