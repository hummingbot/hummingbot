from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://api.btcmarkets.net"
HEALTH_CHECK_ENDPOINT = "/v3/time"
CANDLES_ENDPOINT = "/v3/markets/{market_id}/candles"

WSS_URL = None

INTERVALS = bidict(
    {
        "1m": "1m",
        "3m": "3m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "2h": "2h",
        "3h": "3h",
        "4h": "4h",
        "6h": "6h",
        "1d": "1d",
        "1w": "1w",
        "1M": "1mo",  # BTC Markets uses "1mo" for 1 month
    }
)

POLL_INTERVAL = 5.0  # seconds

MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 1000

# Rate Limits based on BTC Markets documentation
# Using the same rate limits as defined in btc_markets_constants.py
MARKETS_URL = "/v3/markets"
SERVER_TIME_PATH_URL = "/v3/time"

RATE_LIMITS = [
    RateLimit(limit_id=MARKETS_URL, limit=150, time_interval=10),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=50, time_interval=10),
    RateLimit(limit_id=CANDLES_ENDPOINT, limit=50, time_interval=10, linked_limits=[LinkedLimitWeightPair("raw", 1)]),
    RateLimit(
        limit_id=HEALTH_CHECK_ENDPOINT, limit=50, time_interval=10, linked_limits=[LinkedLimitWeightPair("raw", 1)]
    ),
]
