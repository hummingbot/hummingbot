import sys
from enum import Enum

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "architect_perpetual"
DEFAULT_DOMAIN = EXCHANGE_NAME
SANDBOX_DOMAIN = "architect_perpetual_sandbox"
REST_URL_BASES = {
    DEFAULT_DOMAIN: "https://gateway.architect.exchange",
    SANDBOX_DOMAIN: "https://gateway.sandbox.architect.exchange",
}

PUBLIC_WS_URL = {
    DEFAULT_DOMAIN: "wss://gateway.architect.exchange/md/ws",
    SANDBOX_DOMAIN: "wss://gateway.sandbox.architect.exchange/md/ws",
}
PRIVATE_WS_URL = {
    DEFAULT_DOMAIN: "wss://gateway.architect.exchange/orders/ws",
    SANDBOX_DOMAIN: "wss://gateway.sandbox.architect.exchange/orders/ws",
}

MAX_ORDER_ID_BIT_COUNT = 64
FUNDING_FEE_POLL_INTERVAL = 120
FUNDING_RATE_UPDATE_INTERNAL_SECOND = 60

SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 20
WS_HEARTBEAT_TIME_INTERVAL = 30

ORDER_STATUS_MAP = {
    "PENDING": OrderState.PENDING_APPROVAL,
    "ACCEPTED": OrderState.OPEN,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "FILLED": OrderState.FILLED,
    "CANCELED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.CANCELED,
    "REPLACED": OrderState.CANCELED,
    "DONE_FOR_DAY": OrderState.CANCELED,
    "UNKNOWN": OrderState.PENDING_APPROVAL,
}

SERVER_TIME_ENDPOINT = "/api/health"
USER_INFO_ENDPOINT = "/api/whoami"
EXCHANGE_INFO_ENDPOINT = "/api/instruments"
TICKERS_INFO_ENDPOINT = "/api/tickers"
SINGLE_TICKER_INFO_ENDPOINT = "/api/ticker"
PUBLIC_ORDERBOOK_ENDPOINT = "/api/book"
AUTH_TOKEN_ENDPOINT = "/api/authenticate"
FUNDING_INFO_ENDPOINT = "/api/funding-rates"
FUNDING_EVENTS_ENDPOINT = "/api/funding-transactions"
RISK_ENDPOINT = "/api/risk-snapshot"

PLACE_ORDER_ENDPOINT = "/orders/place_order"
CANCEL_ORDER_ENDPOINT = "/orders/cancel_order"
ORDER_STATUS_ENDPOINT = "/orders/order-status"
ORDER_FILLS_ENDPOINT = "/orders/order-fills"

PRIVATE_WS_CONNECTION = "private-ws-connection"


class WSMessageTypes(str, Enum):
    ORDER_BOOK_SNAPSHOT = "2"
    TRADE = "t"


NO_LIMIT = sys.maxsize
ONE_MINUTE = 60
ONE_SECOND = 1

RATE_LIMITS = [
    RateLimit(limit_id=SERVER_TIME_ENDPOINT, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=USER_INFO_ENDPOINT, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=EXCHANGE_INFO_ENDPOINT, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=TICKERS_INFO_ENDPOINT, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=SINGLE_TICKER_INFO_ENDPOINT, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=PUBLIC_ORDERBOOK_ENDPOINT, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=AUTH_TOKEN_ENDPOINT, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=FUNDING_INFO_ENDPOINT, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=FUNDING_EVENTS_ENDPOINT, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=RISK_ENDPOINT, limit=10, time_interval=ONE_SECOND),

    RateLimit(limit_id=PLACE_ORDER_ENDPOINT, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=CANCEL_ORDER_ENDPOINT, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=ORDER_STATUS_ENDPOINT, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=ORDER_FILLS_ENDPOINT, limit=10, time_interval=ONE_SECOND),

    RateLimit(limit_id=PRIVATE_WS_CONNECTION, limit=10, time_interval=ONE_SECOND),
]
