from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://api.gateio.ws/api/v4"
HEALTH_CHECK_ENDPOINT = "/futures/usdt/contracts/BTC_USDT"
CANDLES_ENDPOINT = "/futures/usdt/candlesticks"
CONTRACT_INFO_URL = "/futures/usdt/contracts/{contract}"


WS_CANDLES_ENDPOINT = "futures.candlesticks"

WSS_URL = "wss://fx-ws.gateio.ws/v4/ws/usdt"
INTERVALS = bidict({
    "10s": 10,
    "30s": 30,
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "8h": 28800,
    "12h": 43200,
    "1d": 86400,
    "7d": 604800,
    "1w": 2592000,
})
PUBLIC_URL_POINTS_LIMIT_ID = "PublicPoints"

RATE_LIMITS = [
    RateLimit(limit_id=PUBLIC_URL_POINTS_LIMIT_ID, limit=300, time_interval=1),
    RateLimit(limit_id=HEALTH_CHECK_ENDPOINT, limit=300, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=CANDLES_ENDPOINT, limit=300, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=CONTRACT_INFO_URL, limit=300, time_interval=1,
              linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
]