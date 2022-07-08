# Order States
from decimal import Decimal

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

ORDER_STATE = {
    "OPEN": OrderState.OPEN,
    "CLOSED": OrderState.FILLED,
    "PARTIAL": OrderState.PARTIALLY_FILLED,
    "CANCELED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.FAILED,
}

MIN_ORDER_SIZE = Decimal(10.0)
MIN_PRICE = Decimal(10.0)
MIN_QTY = Decimal(10.0)
TRADE_EVENT_TYPE = "trade"
DIFF_EVENT_TYPE  = "diff"
GRAPHQL_ENDPOINT = "https://x6sbwzrbzvbabpujfy2phgq6ka.appsync-api.ap-south-1.amazonaws.com/graphql"
GRAPHQL_WSS_ENDPOINT = "wss://x6sbwzrbzvbabpujfy2phgq6ka.appsync-realtime-api.ap-south-1.amazonaws.com/graphql"
GRAPHQL_API_KEY = "da2-wlahfkgsznh27ahj253h7oefp4"
ENCLAVE_ENDPOINT = "ws://127.0.0.1:9945"

POLKADEX_SS58_PREFIX = 88

UPDATE_ORDER_STATUS_MIN_INTERVAL = 10

WS_PING_INTERVAL = 30

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS = "ORDERS"
ORDERS_24HR = "ORDERS_24HR"

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400


RATE_LIMITS = [
    # Pools
    RateLimit(limit_id="polkadex", limit=1200, time_interval=ONE_MINUTE),
]

