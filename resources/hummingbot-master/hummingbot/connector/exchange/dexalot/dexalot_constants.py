from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "dexalot"
TESTNET_DOMAIN = "dexalot_testnet"

HBOT_ORDER_ID_PREFIX = "HBOT"
MAX_ORDER_ID_LEN = 64

# Base URL
REST_URL = "https://api.dexalot.com/privapi"
WSS_URL = "wss://api.dexalot.com"
DEXALOT_SUBNET_RPC_URL = "https://subnets.avax.network/dexalot/mainnet/rpc"
DEXALOT_TRADEPAIRS_ADDRESS = "0x09383137C1eEe3E1A8bc781228E4199f6b4A9bbf"
DEXALOT_PORTFOLIOSUB_ADDRESS = "0xa5C079C1986E2335d83fA2d7282e162958e515D5"


TESTNET_REST_URL = "https://api.dexalot-test.com/privapi"
TESTNET_WSS_URL = "wss://api.dexalot-test.com"
TESTNET_DEXALOT_SUBNET_RPC_URL = "https://subnets.avax.network/dexalot/testnet/rpc"
TESTNET_DEXALOT_TRADEPAIRS_ADDRESS = "0xaa3891FEa80967b57AAA4E962d1b07BCEe0b5394"
TESTNET_DEXALOT_PORTFOLIOSUB_ADDRESS = "0xb54859290619630212D4BBAba47066BEE9654076"


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
