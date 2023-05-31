from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://api.gateio.ws/api/v4"
HEALTH_CHECK_ENDPOINT = "/spot/currencies/BTC"
CANDLES_ENDPOINT = "/spot/candlesticks"
WS_CANDLES_ENDPOINT = "spot.candlesticks"

WSS_URL = "wss://api.gateio.ws/ws/v4/"

INTERVALS = bidict({
    "10s": 10,
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "8h": 28800,
    "1d": 86400,
    "7d": 604800,
    "30d": 2592000
})
PUBLIC_URL_POINTS_LIMIT_ID = "PublicPoints"

RATE_LIMITS = [
    RateLimit(limit_id=PUBLIC_URL_POINTS_LIMIT_ID, limit=900, time_interval=1),
    RateLimit(limit_id=HEALTH_CHECK_ENDPOINT, limit=900, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=CANDLES_ENDPOINT, limit=900, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
]