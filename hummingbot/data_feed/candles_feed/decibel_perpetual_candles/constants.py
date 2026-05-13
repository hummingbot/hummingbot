from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

# Base URLs - Mainnet
REST_URL = "https://api.mainnet.aptoslabs.com/decibel"
WSS_URL = "wss://api.mainnet.aptoslabs.com/decibel/ws"

# Netna (Staging)
NETNA_DOMAIN = "decibel_perpetual_netna"
NETNA_REST_URL = "https://api.netna.staging.aptoslabs.com/decibel"
NETNA_WSS_URL = "wss://api.netna.staging.aptoslabs.com/decibel/ws"

# Testnet
TESTNET_DOMAIN = "decibel_perpetual_testnet"
TESTNET_REST_URL = "https://api.testnet.aptoslabs.com/decibel"
TESTNET_WSS_URL = "wss://api.testnet.aptoslabs.com/decibel/ws"

HEALTH_CHECK_ENDPOINT = "/api/v1/markets"
CANDLES_ENDPOINT = "/api/v1/candlesticks"

WS_CANDLES_CHANNEL = "market_candlestick"

# Supported intervals (Decibel supports standard intervals)
INTERVALS = bidict({
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "8h": "8h",
    "12h": "12h",
    "1d": "1d",
})

MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 1000

# Rate limits for candles feed
# Decibel API rate limit: 400 requests per minute (API key required)
DECIBEL_CANDLES_LIMIT_ID = "DECIBEL_CANDLES_LIMIT"
STANDARD_REQUEST_COST = 1

RATE_LIMITS = [
    RateLimit(limit_id=DECIBEL_CANDLES_LIMIT_ID, limit=400, time_interval=60),
    RateLimit(limit_id=HEALTH_CHECK_ENDPOINT, limit=400, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(DECIBEL_CANDLES_LIMIT_ID, weight=STANDARD_REQUEST_COST)]),
    RateLimit(limit_id=CANDLES_ENDPOINT, limit=400, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(DECIBEL_CANDLES_LIMIT_ID, weight=STANDARD_REQUEST_COST)]),
]
