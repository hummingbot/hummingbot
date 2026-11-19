from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://api.gateio.ws/api/v4"
HEALTH_CHECK_ENDPOINT = "/spot/currencies/BTC"
CANDLES_ENDPOINT = "/spot/candlesticks"
WS_CANDLES_ENDPOINT = "spot.candlesticks"

WSS_URL = "wss://api.gateio.ws/ws/v4/"


INTERVALS = bidict({
    "10s": "10s",
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "8h": "8h",
    "1d": "1d",
    "7d": "7d",
    "30d": "30d",
})
# from and to are both inclusive: a window of 999 intervals is 1000 candles, the most Gate returns per request
# (a 1000-interval window is rejected with "Candlestick range too broad. Maximum 1000 data points are allowed per request")
MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 999
MAX_CANDLES_AGO = 10_000
PUBLIC_URL_POINTS_LIMIT_ID = "PublicPoints"
PUBLIC_ENDPOINT_LIMIT = 200

RATE_LIMITS = [
    RateLimit(limit_id=PUBLIC_URL_POINTS_LIMIT_ID, limit=PUBLIC_ENDPOINT_LIMIT, time_interval=2),
    RateLimit(limit_id=HEALTH_CHECK_ENDPOINT, limit=PUBLIC_ENDPOINT_LIMIT, time_interval=2,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=CANDLES_ENDPOINT, limit=PUBLIC_ENDPOINT_LIMIT, time_interval=2,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
]
