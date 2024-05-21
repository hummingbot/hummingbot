from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://fapi.binance.com"
HEALTH_CHECK_ENDPOINT = "/fapi/v1/ping"
EXCHANGE_INFO = "/fapi/v1/exchangeInfo"

WSS_URL = "wss://fstream.binance.com/ws"

REQUEST_WEIGHT = "REQUEST_WEIGHT"

RATE_LIMITS = [
    RateLimit(HEALTH_CHECK_ENDPOINT, limit=1200, time_interval=60, linked_limits=[LinkedLimitWeightPair("raw", 1)]),
    RateLimit(limit_id=EXCHANGE_INFO, limit=1200, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=40)]),
]
