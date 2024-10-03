from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

# Base URLs
REST_URL = "https://api.bitget.com"
HEALTH_CHECK_ENDPOINT = "/api/spot/v1/public/time"
CANDLES_ENDPOINT = "/api/spot/v1/market/candles"

WSS_URL = "wss://ws.bitget.com/spot/v1/stream"

# Interval mappings between Hummingbot and Bitget
INTERVALS = bidict({
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "4h": "4h",
    "6h": "6h",
    "12h": "12h",
    "1d": "1day",
    "1w": "1week",
})

# WebSocket intervals (if applicable)
WS_INTERVALS = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "4h": "4h",
    "6h": "6h",
    "12h": "12h",
    "1d": "1day",
    "1w": "1week",
}

# Maximum number of results per candlestick REST request
MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 200

# Rate Limits
RATE_LIMITS = [
    RateLimit(
        limit_id=CANDLES_ENDPOINT,
        limit=1200,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair("IP_RATE_LIMIT", 1)]
    ),
    RateLimit(
        limit_id=HEALTH_CHECK_ENDPOINT,
        limit=1200,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair("IP_RATE_LIMIT", 1)]
    ),
]
