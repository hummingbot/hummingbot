import sys

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

EXCHANGE_NAME = "phemex_perpetual"

DOMAIN = EXCHANGE_NAME

PERPETUAL_BASE_URL = "https://api.phemex.com"
TESTNET_BASE_URL = "https://testnet-api.phemex.com"

PERPETUAL_WS_URL = "wss://phemex.com"
TESTNET_WS_URL = "wss://testnet.phemex.com"

PUBLIC_WS_ENDPOINT = "/ws"
PRIVATE_WS_ENDPOINT = "/ws"

WS_HEARTBEAT = 5  # https://phemex-docs.github.io/#heartbeat

# Public API Endpoints
SNAPSHOT_REST_URL = "/md/v2/orderbook"
TICKER_PRICE_URL = "/md/v2/ticker/24hr"
TICKER_PRICE_CHANGE_URL = TICKER_PRICE_URL
PING_URL = "/ping"
MARK_PRICE_URL = TICKER_PRICE_URL
SERVER_TIME_PATH_URL = "/public/time"


# Funding Settlement Time Span
FUNDING_SETTLEMENT_DURATION = (0, 30)  # seconds before snapshot, seconds after snapshot


# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS_1MIN = "ORDERS_1MIN"
WSS_CONNECTION_LIMIT_ID = "phemexWSSConnectionLimitID"
WSS_MESSAGE_LIMIT_ID = "phemexWSSMessageLimitID"

DIFF_STREAM_METHOD = "orderbook_p.subscribe"
TRADE_STREAM_METHOD = "trade_p.subscribe"
FUNDING_INFO_STREAM_METHOD = "perp_market24h_pack_p.subscribe"
HEARTBEAT_TIME_INTERVAL = 5.0

# Rate Limit time intervals
ONE_HOUR = 3600
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 5000
NO_LIMIT = sys.maxsize

RATE_LIMITS = [
    # Pool Limits
    RateLimit(limit_id=REQUEST_WEIGHT, limit=100, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS_1MIN, limit=500, time_interval=ONE_MINUTE),
    # Weight Limits for individual endpoints
    RateLimit(limit_id=SNAPSHOT_REST_URL, limit=100, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=TICKER_PRICE_URL, limit=100, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=TICKER_PRICE_CHANGE_URL, limit=100, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=PING_URL, limit=100, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=100, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=MARK_PRICE_URL, limit=100, time_interval=ONE_MINUTE, weight=1,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=WSS_CONNECTION_LIMIT_ID, limit=NO_LIMIT, time_interval=ONE_SECOND),
    RateLimit(limit_id=WSS_MESSAGE_LIMIT_ID, limit=NO_LIMIT, time_interval=ONE_SECOND),
]
