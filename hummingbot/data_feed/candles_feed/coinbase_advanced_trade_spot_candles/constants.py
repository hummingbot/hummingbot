from bidict import bidict

from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_constants import (
    CANDLES_EP,
    CANDLES_EP_ID,
)

CANDLES_ENDPOINT = CANDLES_EP
CANDLES_ENDPOINT_ID = CANDLES_EP_ID

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

MAX_CANDLES_SIZE = 349
