from decimal import Decimal

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "twofinance"
TESTNET_DOMAIN = "twofinance_testnet"

HBOT_ORDER_ID_PREFIX = "HBOT-2F-"
MAX_ORDER_ID_LEN = 64

REST_URL = "http://127.0.0.1:8080/api/v1"
WSS_URL = "ws://127.0.0.1:10000"
TESTNET_REST_URL = REST_URL
TESTNET_WSS_URL = WSS_URL

SYMBOLS_PATH_URL = "/symbols"
TRADING_RULES_PATH_URL = "/trading-rules"
BALANCES_PATH_URL = "/balances"
ORDER_BOOK_PATH_URL = "/order-book/{trading_pair}"
ORDER_STATUS_PATH_URL = "/orders/{client_order_id}"
ORDER_TRADES_PATH_URL = "/orders/{client_order_id}/trades"
EVENTS_PATH_URL = "/events"
PING_PATH_URL = "/health"

WS_PUBLIC_SUBSCRIBE = "subscribe_public"
WS_PRIVATE_SUBSCRIBE = "subscribe_private"

MATCHENGINE_ORDER_COMMAND_SCHEMA = "matchengine.order_command.v1"
MATCHENGINE_EVENT_SCHEMA = "matchengine.event.v1"

IP_REQUEST_WEIGHT = "IP_REQUEST_WEIGHT"
UID_REQUEST_WEIGHT = "UID_REQUEST_WEIGHT"
ONE_SECOND = 1
ONE_MINUTE = 60
MAX_REQUEST = 300

RATE_LIMITS = [
    RateLimit(limit_id=IP_REQUEST_WEIGHT, limit=MAX_REQUEST, time_interval=ONE_MINUTE),
    RateLimit(limit_id=UID_REQUEST_WEIGHT, limit=MAX_REQUEST, time_interval=ONE_MINUTE),
    RateLimit(
        limit_id=SYMBOLS_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(IP_REQUEST_WEIGHT, 1)],
    ),
    RateLimit(
        limit_id=TRADING_RULES_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(IP_REQUEST_WEIGHT, 1)],
    ),
    RateLimit(
        limit_id=BALANCES_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(UID_REQUEST_WEIGHT, 1)],
    ),
    RateLimit(
        limit_id=ORDER_BOOK_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(IP_REQUEST_WEIGHT, 1)],
    ),
    RateLimit(
        limit_id=ORDER_STATUS_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(UID_REQUEST_WEIGHT, 1)],
    ),
    RateLimit(
        limit_id=ORDER_TRADES_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(UID_REQUEST_WEIGHT, 1)],
    ),
    RateLimit(
        limit_id=PING_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=ONE_MINUTE,
        linked_limits=[LinkedLimitWeightPair(IP_REQUEST_WEIGHT, 1)],
    ),
    RateLimit(limit_id=WSS_URL, limit=20, time_interval=ONE_SECOND),
]

ORDER_STATE = {
    "OPEN": OrderState.OPEN,
    "NEW": OrderState.OPEN,
    "ACCEPTED": OrderState.OPEN,
    "PARTIAL": OrderState.PARTIALLY_FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "FILLED": OrderState.FILLED,
    "CANCELED": OrderState.CANCELED,
    "CANCELLED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "FAILED": OrderState.FAILED,
}

DEFAULT_MAKER_FEE = Decimal("0")
DEFAULT_TAKER_FEE = Decimal("0")
