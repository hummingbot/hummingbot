from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://api.gateio.ws/api/v4"
HEALTH_CHECK_ENDPOINT = "/futures/usdt/contracts/BTC_USDT"
CANDLES_ENDPOINT = "/futures/usdt/candlesticks"
CONTRACT_INFO_URL = "/futures/usdt/contracts/{contract}"


WS_CANDLES_ENDPOINT = "futures.candlesticks"

WSS_URL = "wss://fx-ws.gateio.ws/v4/ws/usdt"
INTERVALS = bidict({
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "8h": "8h",
    "1d": "1d",
    "7d": "7d",
})
MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 2000
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
