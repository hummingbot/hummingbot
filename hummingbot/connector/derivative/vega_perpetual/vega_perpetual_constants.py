from typing import Any, Dict

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "vega_perpetual"
BROKER_ID = "VGHB"
MAX_ORDER_ID_LEN = 32

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "vega_perpetual_testnet"

# NOTE: Vega has a number of endpoints, which may have different connectivity / reliability...
PERPETUAL_API_ENDPOINTS = [
    "https://darling.network/",
    "https://graphqlvega.gpvalidator.com/",
    "https://vega-data.bharvest.io/",
    "https://vega-data.nodes.guru:3008/",
    "https://vega-mainnet-data.commodum.io/",
    "https://vega-mainnet.anyvalid.com/",
    "https://vega.aurora-edge.com/",
    "https://vega.mainnet.stakingcabin.com:3008/",
]

TESTNET_API_ENDPOINTS = [
    "https://api.n00.testnet.vega.rocks/",
    "https://api.n06.testnet.vega.rocks/",
    "https://api.n07.testnet.vega.rocks/",
    "https://api.n08.testnet.vega.rocks/",
    "https://api.n09.testnet.vega.rocks/",
    "https://api.n07.testnet.vega.xyz/",
]

PERPETUAL_GRPC_ENDPOINTS = [
    "darling.network:3007",
    "vega-data.bharvest.io:3007",
    "vega-data.nodes.guru:3007",
    "vega-mainnet.anyvalid.com:3007",
    "vega.mainnet.stakingcabin.com:3007",
]

TESTNET_GRPC_ENDPOINTS = [
    "api.n00.testnet.vega.rocks:3007",
    "api.n06.testnet.vega.rocks:3007",
    "api.n07.testnet.vega.rocks:3007",
    "api.n08.testnet.vega.rocks:3007",
    "api.n09.testnet.vega.rocks:3007",
]

PERPETUAL_EXPLORER_ENDPOINTS = [
    'https://be.vega.community/rest/'
]

TESTNET_EXPLORER_ENDPOINTS = [
    'https://be.testnet.vega.xyz/rest/'
]

PERPETUAL_BASE_URL = f"{PERPETUAL_API_ENDPOINTS[0]}"
TESTNET_BASE_URL = f"{TESTNET_API_ENDPOINTS[2]}"

PERPETUAL_WS_URL = f"{PERPETUAL_API_ENDPOINTS[0]}".replace("https", "wss")
TESTNET_WS_URL = f"{TESTNET_API_ENDPOINTS[2]}".replace("https", "wss")

PERPETAUL_EXPLORER_URL = f"{PERPETUAL_EXPLORER_ENDPOINTS[0]}"
TESTNET_EXPLORER_URL = f"{TESTNET_EXPLORER_ENDPOINTS[0]}"

PERPETUAL_GRPC_URL = f"{PERPETUAL_GRPC_ENDPOINTS[0]}"
TESTNET_GRPC_URL = f"{TESTNET_GRPC_ENDPOINTS[2]}"

API_VERSION = "v2"

TIME_IN_FORCE_GTC = "GTC"  # Good till cancelled
TIME_IN_FORCE_GTX = "GTX"  # Good till crossing
TIME_IN_FORCE_GTT = "GTT"  # Good till time
TIME_IN_FORCE_IOC = "IOC"  # Immediate or cancel
TIME_IN_FORCE_FOK = "FOK"  # Fill or kill
TIME_IN_FORCE_GFA = "GFA"  # Good for acution
TIME_IN_FORCE_GFN = "GFN"  # Good for normal

# Market Data Endpoints
SNAPSHOT_REST_URL = "/market/depth"
TICKER_PRICE_URL = "/market/data"
EXCHANGE_INFO_URL = "/markets"
MARKET_DATA_URL = "/market"
SYMBOLS_URL = "/assets"

RECENT_TRADES_URL = "/trades"
PING_URL = "/epoch"
MARK_PRICE_URL = "/market/data"
SERVER_BLOCK_TIME = "/vega/time"
SERVER_TIME_PATH_URL = "/vega/time"
FUNDING_RATE_URL = "/funding-periods"
TRANSACTION_POST_URL = "transaction/raw"

# Account Data Endpoints
# NOTE: These all can be filtered on...
ACCOUNT_INFO_URL = "/accounts"
ORDER_URL = "/order"
ORDER_LIST_URL = "/orders"
TRADE_LIST_URL = "/trades"
ESTIMATE_POSITION_URL = "/estimate/position"
ESTIMATE_MARGIN_URL = "/estimate/margin"
ESTIMATE_FEE_URL = "/estimate/fee"
POSITION_LIST_URL = "/positions"
LEDGER_ENTRY_URL = "/ledgerentry/history"
FUNDING_PAYMENTS_URL = "/funding-payments"

# NOTE: We don't have an endpoint to submit orders / cancel as it's just a
# build transaction / submit transaction system.

RECENT_SUFFIX = "latest"  # NOTE: This is used as a suffix vs historical data...

# Funding Settlement Time Span
FUNDING_SETTLEMENT_DURATION = (0, 30)  # seconds before snapshot, seconds after snapshot

# Order Statuses
ORDER_STATE = {
    "STATUS_UNSPECIFIED": OrderState.PENDING_APPROVAL,  # NOTE: not sure on this one
    "STATUS_ACTIVE": OrderState.OPEN,
    "STATUS_EXPIRED": OrderState.CANCELED,
    "STATUS_CANCELLED": OrderState.CANCELED,
    "STATUS_STOPPED": OrderState.CANCELED,  # NOTE: not sure on this one
    "STATUS_FILLED": OrderState.FILLED,
    "STATUS_REJECTED": OrderState.FAILED,
    "STATUS_PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "STATUS_PARKED": OrderState.PENDING_APPROVAL,  # NOTE: not sure on this one
}


# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"

DIFF_STREAM_URL = "/stream/markets/depth/updates"
SNAPSHOT_STREAM_URL = "/stream/markets/depth"
MARKET_DATA_STREAM_URL = "/stream/markets/data"
TRADE_STREAM_URL = "/stream/trades"
ORDERS_STREAM_URL = "/stream/orders"
POSITIONS_STREAM_URL = "/stream/positions"
ACCOUNT_STREAM_URL = "/stream/accounts"
MARGIN_STREAM_URL = "/stream/margin/levels"
# WS Channels
ACCOUNT_STREAM_ID = "account"
ORDERS_STREAM_ID = "orders"
POSITIONS_STREAM_ID = "positions"
TRADES_STREAM_ID = "trades"
MARGIN_STREAM_ID = "margin"

HEARTBEAT_TIME_INTERVAL = 30.0

# Rate Limit time intervals
ONE_HOUR = 3600
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 20

ALL_URLS = "ALL_URLS"

# NOTE: Review https://github.com/vegaprotocol/vega/blob/develop/datanode/ratelimit/README.md
RATE_LIMITS = [
    RateLimit(limit_id=ALL_URLS, limit=MAX_REQUEST, time_interval=ONE_MINUTE)
]


HummingbotToVegaIntSide: Dict[Any, int] = {
    None: 0,  # SIDE_UNSPECIFIED
    TradeType.BUY: 1,  # SIDE_BUY
    TradeType.SELL: 2,  # SIDE_SELL
}


VegaIntSideToHummingbot: Dict[int, Any] = {
    0: None,  # SIDE_UNSPECIFIED
    1: TradeType.BUY,  # SIDE_BUY
    2: TradeType.SELL  # SIDE_SELL
}


VegaStringSideToHummingbot: Dict[str, Any] = {
    "SIDE_UNSPECIFIED": None,
    "SIDE_BUY": TradeType.BUY,
    "SIDE_SELL": TradeType.SELL,
}


HummingbotToVegaIntOrderType: Dict[Any, Any] = {
    None: 0,  # TYPE_UNSPECIFIED
    "": 3,  # TYPE_NETWORK
    OrderType.MARKET: 2,  # TYPE_MARKET
    OrderType.LIMIT: 1,  # TYPE_LIMIT
    OrderType.LIMIT_MAKER: 1,  # TYPE_LIMIT
}

# NOTE: https://docs.vega.xyz/testnet/api/graphql/enums/order-status
VegaIntOrderStatusToHummingbot = {
    0: OrderState.PENDING_APPROVAL,  # STATUS_UNSPECIFIED
    1: OrderState.OPEN,  # STATUS_ACTIVE
    2: OrderState.CANCELED,  # STATUS_EXPIRED
    3: OrderState.CANCELED,  # STATUS_CANCELLED
    4: OrderState.CANCELED,  # STATUS_STOPPED
    5: OrderState.FILLED,  # STATUS_FILLED
    6: OrderState.FAILED,  # STATUS_REJECTED
    7: OrderState.PARTIALLY_FILLED,  # STATUS_PARTIALLY_FILLED
    8: OrderState.CANCELED,  # STATUS_PARKED
}

VegaStringOrderStatusToHummingbot = {
    "STATUS_UNSPECIFIED": OrderState.PENDING_APPROVAL,  # 0
    "STATUS_ACTIVE": OrderState.OPEN,  # 1
    "STATUS_EXPIRED": OrderState.CANCELED,  # 2
    "STATUS_CANCELLED": OrderState.CANCELED,  # 3
    "STATUS_STOPPED": OrderState.CANCELED,  # 4
    "STATUS_FILLED": OrderState.FILLED,  # 5
    "STATUS_REJECTED": OrderState.FAILED,  # 6
    "STATUS_PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,  # 7
    "STATUS_PARKED": OrderState.CANCELED,  # 8
}


VegaOrderError = {
    0: "ORDER_ERROR_UNSPECIFIED",
    1: "ORDER_ERROR_INVALID_MARKET_ID",
    2: "ORDER_ERROR_INVALID_ORDER_ID",
    3: "ORDER_ERROR_OUT_OF_SEQUENCE",
    4: "ORDER_ERROR_INVALID_REMAINING_SIZE",
    5: "ORDER_ERROR_TIME_FAILURE",
    6: "ORDER_ERROR_REMOVAL_FAILURE",
    7: "ORDER_ERROR_INVALID_EXPIRATION_DATETIME",
    8: "ORDER_ERROR_INVALID_ORDER_REFERENCE",
    9: "ORDER_ERROR_EDIT_NOT_ALLOWED",
    10: "ORDER_ERROR_AMEND_FAILURE",
    11: "ORDER_ERROR_NOT_FOUND",
    12: "ORDER_ERROR_INVALID_PARTY_ID",
    13: "ORDER_ERROR_MARKET_CLOSED",
    14: "ORDER_ERROR_MARGIN_CHECK_FAILED",
    15: "ORDER_ERROR_MISSING_GENERAL_ACCOUNT",
    16: "ORDER_ERROR_INTERNAL_ERROR",
    17: "ORDER_ERROR_INVALID_SIZE",
    18: "ORDER_ERROR_INVALID_PERSISTENCE",
    19: "ORDER_ERROR_INVALID_TYPE",
    20: "ORDER_ERROR_SELF_TRADING",
    21: "ORDER_ERROR_INSUFFICIENT_FUNDS_TO_PAY_FEES",
    22: "ORDER_ERROR_INCORRECT_MARKET_TYPE",
    23: "ORDER_ERROR_INVALID_TIME_IN_FORCE",
    24: "ORDER_ERROR_CANNOT_SEND_GFN_ORDER_DURING_AN_AUCTION",
    25: "ORDER_ERROR_CANNOT_SEND_GFA_ORDER_DURING_CONTINUOUS_TRADING",
    26: "ORDER_ERROR_CANNOT_AMEND_TO_GTT_WITHOUT_EXPIRYAT",
    27: "ORDER_ERROR_EXPIRYAT_BEFORE_CREATEDAT",
    28: "ORDER_ERROR_CANNOT_HAVE_GTC_AND_EXPIRYAT",
    29: "ORDER_ERROR_CANNOT_AMEND_TO_FOK_OR_IOC",
    30: "ORDER_ERROR_CANNOT_AMEND_TO_GFA_OR_GFN",
    31: "ORDER_ERROR_CANNOT_AMEND_FROM_GFA_OR_GFN",
    32: "ORDER_ERROR_CANNOT_SEND_IOC_ORDER_DURING_AUCTION",
    33: "ORDER_ERROR_CANNOT_SEND_FOK_ORDER_DURING_AUCTION",
    34: "ORDER_ERROR_MUST_BE_LIMIT_ORDER",
    35: "ORDER_ERROR_MUST_BE_GTT_OR_GTC",
    36: "ORDER_ERROR_WITHOUT_REFERENCE_PRICE",
    37: "ORDER_ERROR_BUY_CANNOT_REFERENCE_BEST_ASK_PRICE",
    38: "ORDER_ERROR_OFFSET_MUST_BE_GREATER_OR_EQUAL_TO_ZERO",
    39: "ORDER_ERROR_SELL_CANNOT_REFERENCE_BEST_BID_PRICE",
    40: "ORDER_ERROR_OFFSET_MUST_BE_GREATER_THAN_ZERO",
    41: "ORDER_ERROR_SELL_CANNOT_REFERENCE_BEST_BID_PRICE",
    42: "ORDER_ERROR_OFFSET_MUST_BE_GREATER_THAN_ZERO",
    43: "ORDER_ERROR_INSUFFICIENT_ASSET_BALANCE",
    44: "ORDER_ERROR_CANNOT_AMEND_PEGGED_ORDER_DETAILS_ON_NON_PEGGED_ORDER",
    45: "ORDER_ERROR_UNABLE_TO_REPRICE_PEGGED_ORDER",
    46: "ORDER_ERROR_UNABLE_TO_AMEND_PRICE_ON_PEGGED_ORDER",
    47: "ORDER_ERROR_NON_PERSISTENT_ORDER_OUT_OF_PRICE_BOUNDS",
    48: "ORDER_ERROR_TOO_MANY_PEGGED_ORDERS",
    49: "ORDER_ERROR_POST_ONLY_ORDER_WOULD_TRADE",
    50: "ORDER_ERROR_REDUCE_ONLY_ORDER_WOULD_NOT_REDUCE_POSITION",
}
