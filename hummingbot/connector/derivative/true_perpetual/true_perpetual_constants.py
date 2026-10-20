from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "true_perpetual"
DOMAIN = EXCHANGE_NAME
MAX_ORDER_ID_LEN = 48
CLIENT_ORDER_ID_PREFIX = "HBOT"

# One host serves REST and websocket. Docs: https://docs.truefinance.ai/en/docs/bot-api
REST_BASE_URL = "https://app.truefinance.ai"
REST_PREFIX = "/api/bot/v1"
WSS_URL = "wss://app.truefinance.ai/api/ws/perps"

SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 30
HEARTBEAT_TIME_INTERVAL = 20.0

# Public endpoints (no signature)
SERVER_TIME_PATH_URL = "/time"
MARKETS_PATH_URL = "/markets"
MARK_PATH_URL = "/mark"
TICKER_PATH_URL = "/ticker"
ORDERBOOK_PATH_URL = "/orderbook"
BBO_PATH_URL = "/bbo"

# Private endpoints (X-TRUE-KEY / X-TRUE-TS / X-TRUE-SIGN)
KEY_PATH_URL = "/key"
ACCOUNT_PATH_URL = "/account"
POSITIONS_PATH_URL = "/positions"
OPEN_ORDERS_PATH_URL = "/orders"
ORDER_STATUS_PATH_URL = "/orders/{id}"
ORDERS_HISTORY_PATH_URL = "/orders/history"
FILLS_PATH_URL = "/fills"
WS_TOKEN_PATH_URL = "/ws-token"
PLACE_ORDER_PATH_URL = "/orders"
CANCEL_ORDER_PATH_URL = "/orders/{id}"
LEVERAGE_PATH_URL = "/leverage"
STREAM_PATH_URL = "/stream"

# Throttler ids for the templated paths
ORDER_STATUS_LIMIT_ID = "GET_ORDER"
CANCEL_ORDER_LIMIT_ID = "CANCEL_ORDER"

# Websocket topics (public market data; the bot token is required on the upgrade)
WS_ORDERBOOK_TOPIC = "orderbook"
WS_TRADES_TOPIC = "trades"
WS_MARK_TOPIC = "mark"

# Funding settles every 8 hours on TRUE; the markets list carries the 8h rate.
FUNDING_INTERVAL_SECONDS = 8 * 60 * 60

# The key's own limits: 600 reads and 120 writes a minute (BOT_API_READ_PER_MIN / BOT_API_TRADE_PER_MIN).
READ_LIMIT_ID = "TRUE_READ"
TRADE_LIMIT_ID = "TRUE_TRADE"
READ_PER_MINUTE = 600
TRADE_PER_MINUTE = 120
ONE_MINUTE = 60

RATE_LIMITS = [
    RateLimit(limit_id=READ_LIMIT_ID, limit=READ_PER_MINUTE, time_interval=ONE_MINUTE),
    RateLimit(limit_id=TRADE_LIMIT_ID, limit=TRADE_PER_MINUTE, time_interval=ONE_MINUTE),
    # Public reads are not counted against the key but share the read budget here so a bot stays polite.
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=READ_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(READ_LIMIT_ID)]),
    RateLimit(limit_id=MARKETS_PATH_URL, limit=READ_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(READ_LIMIT_ID)]),
    RateLimit(limit_id=MARK_PATH_URL, limit=READ_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(READ_LIMIT_ID)]),
    RateLimit(limit_id=TICKER_PATH_URL, limit=READ_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(READ_LIMIT_ID)]),
    RateLimit(limit_id=ORDERBOOK_PATH_URL, limit=READ_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(READ_LIMIT_ID)]),
    RateLimit(limit_id=BBO_PATH_URL, limit=READ_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(READ_LIMIT_ID)]),
    RateLimit(limit_id=KEY_PATH_URL, limit=READ_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(READ_LIMIT_ID)]),
    RateLimit(limit_id=ACCOUNT_PATH_URL, limit=READ_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(READ_LIMIT_ID)]),
    RateLimit(limit_id=POSITIONS_PATH_URL, limit=READ_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(READ_LIMIT_ID)]),
    RateLimit(limit_id=OPEN_ORDERS_PATH_URL, limit=READ_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(READ_LIMIT_ID)]),
    RateLimit(limit_id=ORDER_STATUS_LIMIT_ID, limit=READ_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(READ_LIMIT_ID)]),
    RateLimit(limit_id=ORDERS_HISTORY_PATH_URL, limit=READ_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(READ_LIMIT_ID)]),
    RateLimit(limit_id=FILLS_PATH_URL, limit=READ_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(READ_LIMIT_ID)]),
    RateLimit(limit_id=WS_TOKEN_PATH_URL, limit=READ_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(READ_LIMIT_ID)]),
    RateLimit(limit_id=PLACE_ORDER_PATH_URL, limit=TRADE_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(TRADE_LIMIT_ID)]),
    RateLimit(limit_id=CANCEL_ORDER_LIMIT_ID, limit=TRADE_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(TRADE_LIMIT_ID)]),
    RateLimit(limit_id=LEVERAGE_PATH_URL, limit=TRADE_PER_MINUTE, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(TRADE_LIMIT_ID)]),
]

# GET /orders/{id} answers one normalized status whether the order rests or is done.
ORDER_STATE = {
    "open": OrderState.OPEN,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "filled": OrderState.FILLED,
    "cancelled": OrderState.CANCELED,
    "canceled": OrderState.CANCELED,
    "expired": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
}

ORDER_NOT_FOUND_ERROR = "order_not_found"
