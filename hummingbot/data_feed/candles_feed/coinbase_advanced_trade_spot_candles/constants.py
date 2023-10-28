from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://api.coinbase.com"
HEALTH_CHECK_ENDPOINT = "/api/v2/time"
CANDLES_ENDPOINT = "/api/v3/brokerage/products/{product_id}/candles"
CANDLES_ENDPOINT_ID = "candles"

WSS_URL = "wss://advanced-trade-ws.coinbase.com/"

# TODO: Understand what this is supposed to be
INTERVALS = bidict({
    "1m": "ONE_MINUTE",
    "5m": "FIVE_MINUTE",
    "15m": "FIFTEEN_MINUTE",
    "30m": "THIRTY_MINUTE",
    "1h": "ONE_HOUR",
    "2h": "TWO_HOUR",
    "6h": "SIX_HOUR",
    "1d": "ONE_DAY",
    # Couldn't understand what INTERVALS is supposed to be
    "ONE_MINUTE": 60,
    "FIVE_MINUTE": 300,
    "FIFTEEN_MINUTE": 900,
    "THIRTY_MINUTE": 1800,
    "ONE_HOUR": 3600,
    "TWO_HOUR": 7200,
    "SIX_HOUR": 21600,
    "ONE_DAY": 86400,
})

REQUEST_WEIGHT = "REQUEST_WEIGHT"

RATE_LIMITS = [
    RateLimit(REQUEST_WEIGHT, limit=30, time_interval=1),
    RateLimit(CANDLES_ENDPOINT_ID, limit=30, time_interval=1, linked_limits=[LinkedLimitWeightPair("raw", 1)]),
    RateLimit(HEALTH_CHECK_ENDPOINT, limit=10000, time_interval=3600, linked_limits=[LinkedLimitWeightPair("raw", 1)])]
