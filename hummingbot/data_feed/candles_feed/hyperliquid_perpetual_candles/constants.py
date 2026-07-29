from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://api.hyperliquid.xyz/info"
HEALTH_CHECK_PAYLOAD = {"type": "meta"}
CANDLES_ENDPOINT = "candleSnapshot"

WSS_URL = "wss://api.hyperliquid.xyz/ws"

INTERVALS = bidict({
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "6h": "6h",
    "12h": "12h",
    "1d": "1d",
    "1w": "1w",
    "1M": "1M",
})

MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 500

# Shared global pool of the hyperliquid_perpetual connector (hyperliquid_perpetual_constants.ALL_ENDPOINTS_LIMIT).
# Matching this limit_id lets the candle feed consume from the connector's pool when they share a throttler.
ALL_ENDPOINTS_LIMIT = "All"

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=1200, time_interval=60),
    RateLimit(REST_URL, limit=1200, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, 1)])
]

PING_TIMEOUT = 30.0
PING_PAYLOAD = {"method": "ping"}
