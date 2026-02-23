from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "grvt_perpetual"
MAX_ORDER_ID_LEN = 32

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "grvt_perpetual_testnet"

# For GRVT, endpoints are split among edge, trade_data and market_data.
# In hummingbot, we typically have a single base URL. Since they are different subdomains,
# we will use base URL paths to handle them.
# Prod endpoints
PROD_EDGE_URL = "https://edge.grvt.io"
PROD_TRADE_URL = "https://trades.grvt.io"
PROD_MARKET_URL = "https://market-data.grvt.io"

PROD_TRADE_WS_URL = "wss://trades.grvt.io/ws"
PROD_MARKET_WS_URL = "wss://market-data.grvt.io/ws"

# Testnet endpoints
TESTNET_EDGE_URL = "https://edge.testnet.grvt.io"
TESTNET_TRADE_URL = "https://trades.testnet.grvt.io"
TESTNET_MARKET_URL = "https://market-data.testnet.grvt.io"

TESTNET_TRADE_WS_URL = "wss://trades.testnet.grvt.io/ws"
TESTNET_MARKET_WS_URL = "wss://market-data.testnet.grvt.io/ws"

# Chain IDs
CHAIN_IDS = {
    DOMAIN: 325,
    TESTNET_DOMAIN: 326
}

# Endpoints
AUTH_URL = "/auth/api_key/login"
EXCHANGE_INFO_URL = "/full/v1/all_instruments"
TICKER_URL = "/full/v1/ticker"
ORDERBOOK_URL = "/full/v1/book"
RECENT_TRADES_URL = "/full/v1/trade"
FUNDING_RATE_URL = "/full/v1/funding"
MARK_PRICE_URL = "/full/v1/mini" # Or ticker for mark price

CREATE_ORDER_URL = "/full/v1/create_order"
CANCEL_ORDER_URL = "/full/v1/cancel_order"
CANCEL_ALL_ORDERS_URL = "/full/v1/cancel_all_orders"
OPEN_ORDERS_URL = "/full/v1/open_orders"
ACCOUNT_SUMMARY_URL = "/full/v1/account_summary"
POSITIONS_URL = "/full/v1/positions"
ORDER_HISTORY_URL = "/full/v1/order_history"
FILL_HISTORY_URL = "/full/v1/fill_history"
SERVER_TIME_URL = "" # Not explicit, we can just use the machine time or extract from headers

# Limits
REQUEST_WEIGHT = "REQUEST_WEIGHT"

# Limit values
MAX_REQUEST = 6000
ONE_MINUTE = 60

RATE_LIMITS = [
    RateLimit(limit_id=REQUEST_WEIGHT, limit=MAX_REQUEST, time_interval=ONE_MINUTE),
    RateLimit(limit_id=AUTH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=EXCHANGE_INFO_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=TICKER_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=ORDERBOOK_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=RECENT_TRADES_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=FUNDING_RATE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=MARK_PRICE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=CREATE_ORDER_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=CANCEL_ORDER_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=CANCEL_ALL_ORDERS_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=OPEN_ORDERS_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=ACCOUNT_SUMMARY_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=POSITIONS_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=ORDER_HISTORY_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
    RateLimit(limit_id=FILL_HISTORY_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1)]),
]

# Order Statuses
ORDER_STATE = {
    "OPEN": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "PARTIAL_FILLED": OrderState.PARTIALLY_FILLED,
    "CANCELED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.FAILED,
}

# Time in force
TIME_IN_FORCE_GTC = "GoodTillTime"
TIME_IN_FORCE_IOC = "ImmediateOrCancel"
TIME_IN_FORCE_FOK = "FillOrKill"
TIME_IN_FORCE_AON = "AllOrNone"

# Custom constants
GRVT_MARKET_DATA_RPC = "market_data_rpc"
GRVT_TRADE_DATA_RPC = "trade_data_rpc"
GRVT_EDGE_RPC = "edge_rpc"

GRVT_MARKET_DATA_WS = "market_data_ws"
GRVT_TRADE_DATA_WS = "trade_data_ws"
