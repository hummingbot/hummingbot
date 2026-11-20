from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

# Live-verified against BingX spot production: the spot market endpoints answer under
# https://open-api.bingx.com (no /openapi prefix). The connector's own REST_URL carries an
# /openapi suffix that the spot market-data paths reject with 100400 "this api is not exist".
REST_URL = "https://open-api.bingx.com"
HEALTH_CHECK_ENDPOINT = "/openApi/spot/v1/ticker/24hr"
CANDLES_ENDPOINT = "/openApi/spot/v2/market/kline"

WSS_URL = "wss://open-api-ws.bingx.com/market"

# Hummingbot interval -> BingX spot WebSocket kline interval. The two surfaces use different
# vocabularies: the REST kline endpoint accepts the Hummingbot strings verbatim
# (1m,3m,5m,15m,30m,1h,2h,4h,6h,8h,12h,1d,3d,1w,1M), while the WS dataType requires
# 1min/3min/5min/15min/30min/60min/2hour.../12hour/1day/3day/1week (live-verified; "1hour"
# and "1w" are rejected, and there is no monthly WS kline, so "1M" is not offered).
INTERVALS = bidict({
    "1m": "1min",
    "3m": "3min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "60min",
    "2h": "2hour",
    "4h": "4hour",
    "6h": "6hour",
    "8h": "8hour",
    "12h": "12hour",
    "1d": "1day",
    "3d": "3day",
    "1w": "1week",
})
MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 1440

# Pool ids mirror the bing_x connector's shared GET pools: when a backing connector is
# attached, throttler.add_rate_limits() skips ids that already exist, so candle traffic and
# connector traffic share the connector's budget instead of getting a second one.
GET_REQUEST_POOL = "GET"
GET_REQUEST_BURST_POOL = "GET_BURST"
GET_REQUEST_MIXED_POOL = "GET_MIXED"

MAX_REQUEST_GET = 6000
MAX_REQUEST_GET_BURST = 70
MAX_REQUEST_GET_MIXED = 400
TWO_MINUTES = 120
ONE_SECOND = 1
SIX_SECONDS = 6

GET_LINKED_LIMITS = [
    LinkedLimitWeightPair(GET_REQUEST_POOL, 1),
    LinkedLimitWeightPair(GET_REQUEST_BURST_POOL, 1),
    LinkedLimitWeightPair(GET_REQUEST_MIXED_POOL, 1),
]

RATE_LIMITS = [
    RateLimit(limit_id=GET_REQUEST_POOL, limit=MAX_REQUEST_GET, time_interval=TWO_MINUTES),
    RateLimit(limit_id=GET_REQUEST_BURST_POOL, limit=MAX_REQUEST_GET_BURST, time_interval=ONE_SECOND),
    RateLimit(limit_id=GET_REQUEST_MIXED_POOL, limit=MAX_REQUEST_GET_MIXED, time_interval=SIX_SECONDS),
    RateLimit(limit_id=CANDLES_ENDPOINT, limit=MAX_REQUEST_GET, time_interval=TWO_MINUTES,
              linked_limits=GET_LINKED_LIMITS),
    RateLimit(limit_id=HEALTH_CHECK_ENDPOINT, limit=MAX_REQUEST_GET, time_interval=TWO_MINUTES,
              linked_limits=GET_LINKED_LIMITS),
]
