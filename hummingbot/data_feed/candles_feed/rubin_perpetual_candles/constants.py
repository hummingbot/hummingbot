from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

# Rubin indexer candles API.
# REST:  GET {rest}/v4/candles/perpetualMarkets/{ticker}?resolution=&limit=&fromISO=&toISO=
# WS:    {ws}  channel "v4_candles", id "{ticker}/{resolution}"
# Candles are returned newest-first and must be sorted ascending by the parser.

API_VERSION = "v4"

# domain name (== CandlesFactory key) -> endpoints
DOMAINS = {
    "rubin_perpetual": {
        "rest": "https://indexer.mainnet.rubin.trade",
        "wss": "wss://indexer.mainnet.rubin.trade/{}/ws".format(API_VERSION),
    },
    "rubin_perpetual_testnet": {
        "rest": "https://indexer.testnet.rubin.trade",
        "wss": "wss://indexer.testnet.rubin.trade/{}/ws".format(API_VERSION),
    },
}
DEFAULT_DOMAIN = "rubin_perpetual"

HEALTH_CHECK_ENDPOINT = "/{}/height".format(API_VERSION)
CANDLES_ENDPOINT = "/{}/candles/perpetualMarkets".format(API_VERSION)  # ticker appended to the path
WS_CHANNEL = "v4_candles"

# Hummingbot interval -> indexer resolution. Only these resolutions are supported by the indexer
# (1H / 1D etc. return HTTP 400 — verified against the live endpoint).
INTERVALS = bidict({
    "1m": "1MIN",
    "5m": "5MINS",
    "15m": "15MINS",
    "30m": "30MINS",
    "1h": "1HOUR",
    "4h": "4HOURS",
    "1d": "1DAY",
})

MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 1000  # verified: limit=1000 OK, 5000 rejected

REQUEST_WEIGHT = "REQUEST_WEIGHT"

RATE_LIMITS = [
    RateLimit(limit_id=REQUEST_WEIGHT, limit=100, time_interval=1),
    RateLimit(limit_id=CANDLES_ENDPOINT, limit=100, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=HEALTH_CHECK_ENDPOINT, limit=100, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
]
