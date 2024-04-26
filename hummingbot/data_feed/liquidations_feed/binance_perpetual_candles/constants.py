from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://fapi.binance.com"
HEALTH_CHECK_ENDPOINT = "/fapi/v1/ping"
CANDLES_ENDPOINT = "/fapi/v1/klines"

WSS_URL = "wss://fstream.binance.com/ws"

REQUEST_WEIGHT = "REQUEST_WEIGHT"

RATE_LIMITS = [
    RateLimit(REQUEST_WEIGHT, limit=1200, time_interval=60),
    RateLimit(HEALTH_CHECK_ENDPOINT, limit=1200, time_interval=60, linked_limits=[LinkedLimitWeightPair("raw", 1)])]
