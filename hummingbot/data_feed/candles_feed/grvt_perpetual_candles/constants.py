from bidict import bidict

from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_constants as CONNECTOR_CONSTANTS

CANDLES_ENDPOINT = CONNECTOR_CONSTANTS.KLINE_PATH_URL
HEALTH_CHECK_ENDPOINT = CONNECTOR_CONSTANTS.INSTRUMENTS_PATH_URL
WS_CANDLES_ENDPOINT = CONNECTOR_CONSTANTS.PUBLIC_WS_CHANNEL_CANDLE
MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 1000
RATE_LIMITS = CONNECTOR_CONSTANTS.RATE_LIMITS

INTERVALS = bidict({
    "1m": "CI_1_M",
    "3m": "CI_3_M",
    "5m": "CI_5_M",
    "15m": "CI_15_M",
    "30m": "CI_30_M",
    "1h": "CI_1_H",
    "2h": "CI_2_H",
    "4h": "CI_4_H",
    "6h": "CI_6_H",
    "8h": "CI_8_H",
    "12h": "CI_12_H",
    "1d": "CI_1_D",
    "3d": "CI_3_D",
    "1w": "CI_1_W",
})
