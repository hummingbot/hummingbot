from hummingbot.connector.constants import MINUTE, SECOND
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

DEFAULT_DOMAIN = "derive"
BROKER_ID = "HBOT"

HBOT_ORDER_ID_PREFIX = "x-MG43PCSN"
MAX_ORDER_ID_LEN = 32

RPC_ENDPOINT = "https://rpc.lyra.finance"
TRADE_MODULE_ADDRESS = "0xB8D20c2B7a1Ad2EE33Bc50eF10876eD3035b5e7b"
DOMAIN_SEPARATOR = "0xd96e5f90797da7ec8dc4e276260c7f3f87fedf68775fbe1ef116e996fc60441b" # noqa: mock
ACTION_TYPEHASH = "0x4d7a9f27c403ff9c0f19bce61d76d82f9aa29f8d6d4b0c5474607d9770d1af17" # noqa: mock
CHAIN_ID = 957

TESTNET_RPC_ENDPOINT = "https://rpc-prod-testnet-0eakp60405.t.conduit.xyz"
TESTNET_DOMAIN_SEPARATOR = "0x9bcf4dc06df5d8bf23af818d5716491b995020f377d3b7b64c29ed14e3dd1105" # noqa: mock
TESTNET_ACTION_TYPEHASH = "0x4d7a9f27c403ff9c0f19bce61d76d82f9aa29f8d6d4b0c5474607d9770d1af17"  # noqa: mock
TESTNET_CHAIN_ID = 901

# Base URL
BASE_URL = "https://api.lyra.finance"
WSS_URL = "wss://api.lyra.finance/ws"

TESTNET_BASE_URL = "https://api-demo.lyra.finance"
TESTNET_WSS_URL = "wss://api-demo.lyra.finance/ws"

# Public API endpoints or DeriveClient function
TICKER_PRICE_CHANGE_PATH_URL = "/public/get_ticker"
TICKER_BOOK_PATH_URL = "/public/get_ticker"
PRICES_PATH_URL = "/public/get_ticker"
EXCHANGE_INFO_PATH_URL = "/public/get_all_currencies"
EXCHHANGE_CURRENCIES_PATH_URL = "/public/get_all_instruments"
PING_PATH_URL = "/public/get_time"
SNAPSHOT_PATH_URL = "/public/get_ticker"
SERVER_TIME_PATH_URL = "/public/get_time"

# Private API endpoints or DeriveClient function
ACCOUNTS_PATH_URL = "/private/get_all_portfolios"
MY_TRADES_PATH_URL = "/private/get_trade_history"
CREATE_ORDER_URL = "/private/order"
CANCEL_ORDER_URL = "/private/cancel_order"
ORDER_STATUS_PAATH_URL = "/private/get_order"
ORDER_STATUS_TYPE = "/orderStatus"

WS_PING_REQUEST = "ping"


ALL_ORDERS_PATH_URL = "/private/get_orders"
OPEN_ORDERS_PATH_URL = "/private/get_open_orders"

DERIVE_USER_STREAM_PATH_URL = "/userDataStream"

# Rate Limit IDs
CREATE_ORDER_RATE_LIMIT_ID = "DeriveCreateOrderRateLimitId"
CANCEL_ORDER_RATE_LIMIT_ID = "DeriveCancelOrderRateLimitId"
ORDER_STATUS_RATE_LIMIT_ID = "DeriveOrderStatusRateLimitId"

WS_HEARTBEAT_TIME_INTERVAL = 10

WS_CONNECTIONS_RATE_LIMIT = "WS_CONNECTIONS"

# Derive params

SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

TIME_IN_FORCE_GTC = "GTC"  # Good till cancelled
TIME_IN_FORCE_IOC = "IOC"  # Immediate or cancel
TIME_IN_FORCE_FOK = "FOK"  # Fill or kill

# Rate Limit Type
# Rate Limit Type
GENERAL = "general"
ORDERS_IP = "orders_ip_seconds"
ORDERS_USER = "orders_user_seconds"

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 5000

# Order States
ORDER_STATE = {
    "open": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "cancelled": OrderState.CANCELED,
    "expired": OrderState.FAILED,
    "untriggered": OrderState.FAILED,
}

# Websocket event types
DIFF_EVENT_TYPE = "depthUpdate"
SNAPSHOT_EVENT_TYPE = "depthUpdate"
TRADE_EVENT_TYPE = "trade"

USER_ORDERS_ENDPOINT_NAME = "orders"
USEREVENT_ENDPOINT_NAME = "trades"

RATE_LIMITS = [
    # Pools - will be updated in exchange info initialization
    RateLimit(limit_id=GENERAL, limit=MAX_REQUEST, time_interval=MINUTE),
    RateLimit(limit_id=ORDERS_IP, limit=750, time_interval=6 * SECOND),
    RateLimit(limit_id=ORDERS_USER, limit=200, time_interval=10 * SECOND),
    # Weighted Limits
    RateLimit(
        limit_id=WSS_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(GENERAL, 40)],
    ),
    RateLimit(
        limit_id=TICKER_PRICE_CHANGE_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(GENERAL, 40)],
    ),
    RateLimit(
        limit_id=TICKER_BOOK_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(GENERAL, 1)],
    ),
    RateLimit(
        limit_id=EXCHANGE_INFO_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(GENERAL, 1)],
    ),
    RateLimit(
        limit_id=EXCHHANGE_CURRENCIES_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(GENERAL, 1)],
    ),
    RateLimit(
        limit_id=SNAPSHOT_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(GENERAL, 10)],
    ),
    RateLimit(
        limit_id=DERIVE_USER_STREAM_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(GENERAL, 1)],
    ),
    RateLimit(
        limit_id=SERVER_TIME_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(GENERAL, 1)],
    ),
    RateLimit(
        limit_id=PING_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(GENERAL, 1)],
    ),
    RateLimit(
        limit_id=ACCOUNTS_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(ORDERS_IP, 5), LinkedLimitWeightPair(ORDERS_USER, 5)],
    ),
    RateLimit(
        limit_id=CREATE_ORDER_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(ORDERS_IP, 5), LinkedLimitWeightPair(ORDERS_USER, 5)],
    ),
    RateLimit(
        limit_id=CANCEL_ORDER_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(ORDERS_IP, 5), LinkedLimitWeightPair(ORDERS_USER, 5)],
    ),
    RateLimit(
        limit_id=ORDER_STATUS_PAATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(ORDERS_IP, 5), LinkedLimitWeightPair(ORDERS_USER, 5)],
    ),
    RateLimit(
        limit_id=MY_TRADES_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(ORDERS_IP, 1), LinkedLimitWeightPair(ORDERS_USER, 1)],
    ),
    RateLimit(
        limit_id=CREATE_ORDER_RATE_LIMIT_ID,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(ORDERS_IP, 1), LinkedLimitWeightPair(ORDERS_USER, 1)],
    ),
    RateLimit(
        limit_id=CANCEL_ORDER_RATE_LIMIT_ID,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(ORDERS_IP, 1), LinkedLimitWeightPair(ORDERS_USER, 1)],
    ),
    RateLimit(
        limit_id=ORDER_STATUS_RATE_LIMIT_ID,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(ORDERS_IP, 1), LinkedLimitWeightPair(ORDERS_USER, 1)],
    ),
    RateLimit(
        limit_id=ALL_ORDERS_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(ORDERS_IP, 5), LinkedLimitWeightPair(ORDERS_USER, 5)],
    ),
    RateLimit(
        limit_id=OPEN_ORDERS_PATH_URL,
        limit=MAX_REQUEST,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(ORDERS_IP, 5), LinkedLimitWeightPair(ORDERS_USER, 5)],
    ),
    RateLimit(
        limit_id=WS_CONNECTIONS_RATE_LIMIT,
        limit=300,
        time_interval=5 * MINUTE,
    ),
]
ORDER_NOT_EXIST_ERROR_CODE = -2013
ORDER_NOT_EXIST_MESSAGE = "Order does not exist"
UNKNOWN_ORDER_ERROR_CODE = -2011
UNKNOWN_ORDER_MESSAGE = "Unknown order sent"
