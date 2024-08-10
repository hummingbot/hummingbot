from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://api.kraken.com"
HEALTH_CHECK_ENDPOINT = "/0/public/Time"
CANDLES_ENDPOINT = "/0/public/OHLC"
WS_CANDLES_ENDPOINT = "ohlc"

WSS_URL = "wss://ws.kraken.com"
KRAKEN_TO_HB_MAP = {
    "XBT": "BTC",
    "XDG": "DOGE",
}

INTERVALS = bidict({
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "4h": "240",
    "1d": "1440",
    "1w": "10080",
})
MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = MAX_CANDLES_AGO = 720
PUBLIC_ENDPOINT_LIMIT_ID = "PublicPoints"
RATE_LIMITS = [
    RateLimit(
        limit_id=PUBLIC_ENDPOINT_LIMIT_ID,
        limit=1,
        time_interval=1,
    ),
    # Public Endpoints
    RateLimit(
        limit_id=CANDLES_ENDPOINT,
        limit=1,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_ENDPOINT_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=HEALTH_CHECK_ENDPOINT,
        limit=1,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_ENDPOINT_LIMIT_ID)],
    )
]
