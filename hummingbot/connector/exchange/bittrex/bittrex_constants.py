# A SINGLE POINT OF TRUTH FOR BITTREX
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "Bittrex"
PING_TIMEOUT = 10.0
MAX_RETRIES = 20
MESSAGE_TIMEOUT = 30.0
SNAPSHOT_TIMEOUT = 10.0

BITTREX_REST_URL = "https://api.bittrex.com/v3"
BITTREX_WS_URL = "https://socket-v3.bittrex.com/signalr"
DEFAULT_DOMAIN = ""

# WEBSOCKET CHANNEl KEYS
TRADE_EVENT_KEY = "trade"
DIFF_EVENT_KEY = "orderbook_25"

# Order States
ORDER_STATE = {
    "OPEN": OrderState.OPEN,
    "OPEN-PARTIAL": OrderState.PARTIALLY_FILLED,
    "CLOSED-CANCELLED": OrderState.CANCELED,
    "CLOSED-FILLED": OrderState.FILLED
}

# SERVER REFERENCE DATA URLS
SERVER_TIME_URL = "/ping"

# SERVER UTILITY URLS
BALANCES_URL = "/balances"
ORDERBOOK_SNAPSHOT_URL = "/markets/{}/orderbook"
EXCHANGE_INFO_PATH_URL = "/markets"
ORDER_CREATION_URL = "/orders"
ALL_TRADES_URL = "/executions"
ORDER_DETAIL_URL = "/orders/{}"
ALL_OPEN_ORDERS_URL = "/orders/open"
ALL_CLOSED_ORDERS_URL = "/orders/closed"
SYMBOL_TICKER_PATH = "/markets/{}/ticker"
FEES_URL = "/account/fees/trading"

# RATE-LIMIT ID
ORDERBOOK_SNAPSHOT_LIMIT_ID = "orderBook"
ORDER_DETAIL_LIMIT_ID = "orderDel"
SYMBOL_TICKER_LIMIT_ID = "ticker"

RATE_LIMITS = [
    RateLimit(limit_id=ORDERBOOK_SNAPSHOT_LIMIT_ID, limit=60, time_interval=60),
    RateLimit(limit_id=SERVER_TIME_URL, limit=60, time_interval=60),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=60, time_interval=60),
    RateLimit(limit_id=ORDER_CREATION_URL, limit=60, time_interval=60),
    RateLimit(limit_id=ORDER_DETAIL_LIMIT_ID, limit=60, time_interval=60),
    RateLimit(limit_id=ALL_OPEN_ORDERS_URL, limit=60, time_interval=60),
    RateLimit(limit_id=ALL_CLOSED_ORDERS_URL, limit=60, time_interval=60),
    RateLimit(limit_id=SYMBOL_TICKER_LIMIT_ID, limit=60, time_interval=60),
    RateLimit(limit_id=FEES_URL, limit=60, time_interval=60),
    RateLimit(limit_id=BALANCES_URL, limit=60, time_interval=60),
    RateLimit(limit_id=ALL_TRADES_URL, limit=60, time_interval=60),

]
