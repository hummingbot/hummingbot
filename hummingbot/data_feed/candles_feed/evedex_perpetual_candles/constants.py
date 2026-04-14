from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

MARKET_DATA_REST_URL = "https://market-data-api.evedex.com"
EXCHANGE_REST_URL = "https://exchange-api.evedex.com"
WSS_URL = "wss://ws.evedex.com/connection/websocket"

HEALTH_CHECK_ENDPOINT = "/api/ping"
INSTRUMENTS_ENDPOINT = "/api/market/instrument"
CANDLES_ENDPOINT = "/api/history/{instrument}/list"

WS_HEARTBEAT_TIME_INTERVAL = 25
WS_PING_TIMEOUT = 10

MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 1000

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
    "8h": "8h",
    "12h": "12h",
    "1d": "1d",
    "3d": "3d",
    "1w": "1w",
    "1M": "1M",
})

REQUEST_WEIGHT = "REQUEST_WEIGHT"

RATE_LIMITS = [
    RateLimit(limit_id=REQUEST_WEIGHT, limit=1200, time_interval=60),
    RateLimit(
        limit_id=HEALTH_CHECK_ENDPOINT,
        limit=1200,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)],
    ),
    RateLimit(
        limit_id=INSTRUMENTS_ENDPOINT,
        limit=1200,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)],
    ),
    RateLimit(
        limit_id=CANDLES_ENDPOINT,
        limit=1200,
        time_interval=60,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)],
    ),
]
