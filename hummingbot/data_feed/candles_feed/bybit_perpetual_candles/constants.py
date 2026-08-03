from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://api.bybit.com"
HEALTH_CHECK_ENDPOINT = "/v5/market/time"
CANDLES_ENDPOINT = "/v5/market/kline"

WSS_URL = "wss://stream.bybit.com/v5/public"

INTERVALS = bidict({
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "2h": 120,
    "4h": 240,
    "6h": 360,
    "12h": 720,
    "1d": "D",
    "1w": "W",
    "1M": "M"
})

MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 1000

# Shared GET pool of the bybit_perpetual connector (bybit_perpetual_constants.GET_LIMIT_ID).
# Matching this limit_id lets the candle feed consume from the connector's pool when they share a throttler.
GET_LIMIT_ID = "GETLimit"
GET_RATE = 49  # per second

RATE_LIMITS = [
    RateLimit(GET_LIMIT_ID, limit=GET_RATE, time_interval=1),
    RateLimit(CANDLES_ENDPOINT, limit=20000, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(GET_LIMIT_ID, 1)]),
    RateLimit(HEALTH_CHECK_ENDPOINT, limit=20000, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(GET_LIMIT_ID, 1)])]
