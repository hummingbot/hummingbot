from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "dexalot"

HBOT_ORDER_ID_PREFIX = "HBOT"
MAX_ORDER_ID_LEN = 64

# Base URL
REST_URL = "https://api.dexalot.com/privapi"
WSS_URL = "wss://api.dexalot.com"
DEXALOT_SUBNET_RPC_URL = "https://subnets.avax.network/dexalot/mainnet/rpc"

# Public API endpoints or DexalotClient function
EXCHANGE_INFO_PATH_URL = "/trading/pairs"
TOKEN_INFO_PATH_URL = "/trading/tokens"
PING_PATH_URL = "/trading/environments"

# Private API endpoints or Dexalot function
ACCOUNTS_PATH_URL = "/signed/portfoliobalance"
MY_TRADES_PATH_URL = "/signed/executions"
ORDER_PATH_URL = "/signed/orders/{}"
ORDERS_PATH_URL = "/signed/orders"

WS_HEARTBEAT_TIME_INTERVAL = 30

# Dexalot params


# Market slippage
MARKET_ORDER_SLIPPAGE = 0.05

# gas limit
CANCEL_GAS_LIMIT = 500000
PLACE_ORDER_GAS_LIMIT = 700000

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

TRANSACTION_REQUEST_ATTEMPTS = 5
RETRY_INTERVAL = 2

MAX_REQUEST = 200

# Order States
ORDER_STATE = {
    "NEW": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "PARTIAL": OrderState.PARTIALLY_FILLED,
    "CANCELED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.FAILED,
}

USER_TRADES_ENDPOINT_NAME = "executionEvent"
USER_ORDERS_ENDPOINT_NAME = "orderStatusUpdateEvent"

# Rate Limit Type
# There is no official rate limit
IP_REQUEST_WEIGHT = "IP_REQUEST_WEIGHT"
UID_REQUEST_WEIGHT = "UID_REQUEST_WEIGHT"

RATE_LIMITS = [
    RateLimit(limit_id=IP_REQUEST_WEIGHT, limit=200, time_interval=ONE_MINUTE),
    RateLimit(limit_id=UID_REQUEST_WEIGHT, limit=200, time_interval=ONE_MINUTE),
    # Weighted Limits
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(IP_REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=PING_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(IP_REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(UID_REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=WSS_URL, limit=5, time_interval=ONE_SECOND)
]
