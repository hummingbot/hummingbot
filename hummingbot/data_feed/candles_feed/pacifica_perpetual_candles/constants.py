from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://api.pacifica.fi/api/v1"
WSS_URL = "wss://ws.pacifica.fi/ws"

HEALTH_CHECK_ENDPOINT = "/info"
CANDLES_ENDPOINT = "/kline"

WS_CANDLES_CHANNEL = "candle"

# Supported intervals based on Pacifica's WebSocket documentation
# 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 8h, 12h, 1d
INTERVALS = bidict({
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "8h": "8h",
    "12h": "12h",
    "1d": "1d",
})

MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 1000

# Rate limits for candles feed (public data - no authentication required)
# Using Unidentified IP tier: 125 credits/60s
# Credit costs for unidentified IP:
# - Standard request: 1 credit
# - Heavy GET requests: 3-12 credits
# Documentation: https://docs.pacifica.fi/api-documentation/api/rate-limits
PACIFICA_CANDLES_LIMIT_ID = "PACIFICA_CANDLES_LIMIT"
HEAVY_GET_REQUEST_COST = 12  # Conservative estimate for heavy GET (max for unidentified IP)

RATE_LIMITS = [
    RateLimit(limit_id=PACIFICA_CANDLES_LIMIT_ID, limit=125, time_interval=60),
    RateLimit(limit_id=HEALTH_CHECK_ENDPOINT, limit=125, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(PACIFICA_CANDLES_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST)]),
    RateLimit(limit_id=CANDLES_ENDPOINT, limit=125, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(PACIFICA_CANDLES_LIMIT_ID, weight=HEAVY_GET_REQUEST_COST)]),
]
