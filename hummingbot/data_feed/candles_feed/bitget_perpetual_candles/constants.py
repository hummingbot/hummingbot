from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://api.bitget.com"
WSS_URL = "wss://ws.bitget.com/v2/ws/public"

HEALTH_CHECK_ENDPOINT = "/api/v2/public/time"
CANDLES_ENDPOINT = "/api/v2/mix/market/candles"
WS_CANDLES_ENDPOINT = "candle"
PUBLIC_WS_PING_REQUEST = "ping"

WS_HEARTBEAT_TIME_INTERVAL = 30

MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 1000

INTERVAL_LIMITS_DAYS = {
    "1m": 30,
    "3m": 30,
    "5m": 30,
    "15m": 52,
    "30m": 62,
    "1h": 83,
    "2h": 120,
    "4h": 240,
    "6h": 360
}

USDT_PRODUCT_TYPE = "USDT-FUTURES"
USDC_PRODUCT_TYPE = "USDC-FUTURES"
USD_PRODUCT_TYPE = "COIN-FUTURES"

INTERVALS = bidict({
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1H",
    "4h": "4H",
    "6h": "6H",
    "12h": "12H",
    "1d": "1D",
    "3d": "3D",
    "1w": "1W",
    "1M": "1M"
})

RATE_LIMITS = [
    RateLimit(CANDLES_ENDPOINT, limit=20, time_interval=1, linked_limits=[LinkedLimitWeightPair("raw", 1)]),
    RateLimit(HEALTH_CHECK_ENDPOINT, limit=10, time_interval=1, linked_limits=[LinkedLimitWeightPair("raw", 1)])
]
