from bidict import bidict

from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_constants import (
    MAX_PUBLIC_REST_REQUESTS_S,
    PUBLIC_REST_REQUESTS,
    RATE_LIMITS,
)
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

CANDLES_ENDPOINT = "/brokerage/market/products/{product_id}/candles"
CANDLES_ENDPOINT_ID = "candles"

INTERVALS = bidict({
    "1m": "ONE_MINUTE",
    "5m": "FIVE_MINUTE",
    "15m": "FIFTEEN_MINUTE",
    "30m": "THIRTY_MINUTE",
    "1h": "ONE_HOUR",
    "2h": "TWO_HOUR",
    "6h": "SIX_HOUR",
    "1d": "ONE_DAY",
})

WS_INTERVALS = bidict({
    "5m": "FIVE_MINUTE",
})

MAX_CANDLES_SIZE = 350

RATE_LIMITS.append(
    RateLimit(
        CANDLES_ENDPOINT_ID,
        limit=MAX_PUBLIC_REST_REQUESTS_S - 1,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(PUBLIC_REST_REQUESTS, 1)]),
)
