from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "hyperliquid_perpetual"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = 32

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "hyperliquid_perpetual_testnet"
# yes
PERPETUAL_BASE_URL = "https://api.hyperliquid.xyz"

TESTNET_BASE_URL = "https://api.hyperliquid-testnet.xyz"

PERPETUAL_WS_URL = "wss://api.hyperliquid.xyz/ws"

TESTNET_WS_URL = "wss://api.hyperliquid-testnet.xyz/ws"

FUNDING_RATE_INTERNAL_MIL_SECOND = 10 * 1000

CURRENCY = "USD"
# yes
META_INFO = "meta"
# yes
ASSET_CONTEXT_TYPE = "metaAndAssetCtxs"
# yes
TRADES_TYPE = "userFills"
# yes
ORDER_STATUS_TYPE = "orderStatus"
# yes
USER_STATE_TYPE = "clearinghouseState"

#yes
TICKER_PRICE_CHANGE_URL = "/info"
#yes
SNAPSHOT_REST_URL = "/info"
# yes
EXCHANGE_INFO_URL = "/info"
# yes
CANCEL_ORDER_URL = "/exchange"
# yes
CREATE_ORDER_URL = "/exchange"
# yes
ACCOUNT_TRADE_LIST_URL = "/info"
# yes
ORDER_URL = "/info"
# yes
ACCOUNT_INFO_URL = "/info"
# yes
POSITION_INFORMATION_URL = "/info"
# yes
SET_LEVERAGE_URL = "/exchange"
# yes
GET_LAST_FUNDING_RATE_PATH_URL = "/info"
# yes
PING_URL = "/info"
#yes
SIGNATURE_TYPE = {
    "orderl_by_cloid": ["(uint32,bool,uint64,uint64,bool,uint8,uint64,bytes16)[]", "uint8"],
    "cancel_by_cloid": ["(uint32,bytes16)[]"],
    "updateLeverage": ["uint32", "bool", "uint32"],
}


USER_ORDERS_ENDPOINT_NAME = "orderUpdates"
USEREVENT_ENDPOINT_NAME = "user"

# Order Statuses
# todo 需要根据返回结果填写status。
ORDER_STATE = {
    "open": OrderState.OPEN,
    "resting": OrderState.OPEN,
    "filled": OrderState.FILLED,
    "canceled": OrderState.CANCELED,
    # "expired": OrderState.CANCELED,
    # "rejected": OrderState.FAILED,
}


HEARTBEAT_TIME_INTERVAL = 30.0

MAX_REQUEST = 1_200
ALL_ENDPOINTS_LIMIT = "All"

RATE_LIMITS = [
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=MAX_REQUEST, time_interval=60),
    
    # Weight Limits for individual endpoints
    RateLimit(limit_id=SNAPSHOT_REST_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=TICKER_PRICE_CHANGE_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=EXCHANGE_INFO_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=PING_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=CREATE_ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=CANCEL_ORDER_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),

    RateLimit(limit_id=ACCOUNT_TRADE_LIST_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=SET_LEVERAGE_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=ACCOUNT_INFO_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=POSITION_INFORMATION_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    RateLimit(limit_id=GET_LAST_FUNDING_RATE_PATH_URL, limit=MAX_REQUEST, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT)]),
    
]