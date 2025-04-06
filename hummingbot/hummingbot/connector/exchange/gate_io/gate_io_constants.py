# A single source of truth for constant variables related to the exchange
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

EXCHANGE_NAME = "gate_io"
DEFAULT_DOMAIN = ""
HBOT_BROKER_ID = "hummingbot"
HBOT_ORDER_ID = "t-HBOT"
MAX_ID_LEN = 30

REST_URL = "https://api.gateio.ws/api/v4"
REST_URL_AUTH = "/api/v4"
WS_URL = "wss://api.gateio.ws/ws/v4/"
NETWORK_CHECK_PATH_URL = "spot/currencies/BTC"
SYMBOL_PATH_URL = "spot/currency_pairs"
ORDER_CREATE_PATH_URL = "spot/orders"
ORDER_DELETE_PATH_URL = "spot/orders/{order_id}"
USER_BALANCES_PATH_URL = "spot/accounts"
ORDER_STATUS_PATH_URL = "spot/orders/{order_id}"
USER_ORDERS_PATH_URL = "spot/open_orders"
TICKER_PATH_URL = "spot/tickers"
ORDER_BOOK_PATH_URL = "spot/order_book"
MY_TRADES_PATH_URL = "spot/my_trades"
SERVER_TIME_URL = "spot/time"

TRADES_ENDPOINT_NAME = "spot.trades"
ORDER_SNAPSHOT_ENDPOINT_NAME = "spot.order_book"
ORDERS_UPDATE_ENDPOINT_NAME = "spot.order_book_update"
USER_TRADES_ENDPOINT_NAME = "spot.usertrades"
USER_ORDERS_ENDPOINT_NAME = "spot.orders"
USER_BALANCE_ENDPOINT_NAME = "spot.balances"
PONG_CHANNEL_NAME = "spot.pong"

# Timeouts
MESSAGE_TIMEOUT = 30.0
PING_TIMEOUT = 10.0
API_CALL_TIMEOUT = 10.0
API_MAX_RETRIES = 4

# Intervals
# Only used when nothing is received from WS
SHORT_POLL_INTERVAL = 5.0
# 45 seconds should be fine since we get trades, orders and balances via WS
LONG_POLL_INTERVAL = 45.0
# One minute should be fine since we get trades, orders and balances via WS
UPDATE_ORDER_STATUS_INTERVAL = 60.0
# 10 minute interval to update trading rules, these would likely never change whilst running.
INTERVAL_TRADING_RULES = 600

PUBLIC_URL_POINTS_LIMIT_ID = "PublicPoints"
PRIVATE_URL_POINTS_LIMIT_ID = "PrivatePoints"  # includes place-orders
CANCEL_ORDERS_LIMITS_ID = "CancelOrders"
ORDER_DELETE_LIMIT_ID = "OrderDelete"
ORDER_STATUS_LIMIT_ID = "OrderStatus"
RATE_LIMITS = [
    RateLimit(limit_id=PUBLIC_URL_POINTS_LIMIT_ID, limit=900, time_interval=1),
    RateLimit(limit_id=PRIVATE_URL_POINTS_LIMIT_ID, limit=900, time_interval=1),
    RateLimit(limit_id=CANCEL_ORDERS_LIMITS_ID, limit=5_000, time_interval=1),
    RateLimit(limit_id=NETWORK_CHECK_PATH_URL, limit=900, time_interval=1, linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=SYMBOL_PATH_URL, limit=900, time_interval=1, linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=ORDER_CREATE_PATH_URL, limit=900, time_interval=1, linked_limits=[LinkedLimitWeightPair(PRIVATE_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=ORDER_DELETE_LIMIT_ID, limit=5_000, time_interval=1, linked_limits=[LinkedLimitWeightPair(CANCEL_ORDERS_LIMITS_ID)]),
    RateLimit(limit_id=USER_BALANCES_PATH_URL, limit=900, time_interval=1, linked_limits=[LinkedLimitWeightPair(PRIVATE_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=ORDER_STATUS_LIMIT_ID, limit=900, time_interval=1, linked_limits=[LinkedLimitWeightPair(PRIVATE_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=USER_ORDERS_PATH_URL, limit=900, time_interval=1, linked_limits=[LinkedLimitWeightPair(PRIVATE_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=TICKER_PATH_URL, limit=900, time_interval=1, linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=ORDER_BOOK_PATH_URL, limit=900, time_interval=1, linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=MY_TRADES_PATH_URL, limit=900, time_interval=1, linked_limits=[LinkedLimitWeightPair(PRIVATE_URL_POINTS_LIMIT_ID)]),
    RateLimit(limit_id=SERVER_TIME_URL, limit=900, time_interval=1, linked_limits=[LinkedLimitWeightPair(PUBLIC_URL_POINTS_LIMIT_ID)]),
]

# ERROR LABELS, see https://www.gate.io/docs/developers/apiv4/#label-list
ERR_LABEL_ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
ERR_LABEL_TIME_RELATED_ERROR = "REQUEST_EXPIRED"
