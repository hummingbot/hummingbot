from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://ascendex.com/api/pro/v1/"
HEALTH_CHECK_ENDPOINT = "risk-limit-info"
CANDLES_ENDPOINT = "barhist"
SUB_ENDPOINT_NAME = "sub"

WSS_URL = "wss://ascendex.com:443/api/pro/v1/websocket-for-hummingbot-liq-mining/stream"

# Plesae note that the one-month bar (1m) always resets at the month start.
# The intervalInMillis value for the one-month bar is only indicative.
INTERVALS = bidict({
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "2h": "120",
    "4h": "240",
    "6h": "360",
    "12h": "720",
    "1d": "1d",
    "1w": "1w",
    "1M": "1m"
})
MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 500
ALL_ENDPOINTS_LIMIT = "All"

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=100, time_interval=1),
    RateLimit(CANDLES_ENDPOINT, limit=100, time_interval=1, linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(HEALTH_CHECK_ENDPOINT, limit=100, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)])]
