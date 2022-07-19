from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState

MAX_ID_BIT_COUNT = 63  # experimentally, 64 bit ints sometimes result in OMS assigning order IDs of zero
MAX_ORDER_NOT_FOUND_ON_CANCEL = 2

# rest endpoints
REST_AUTH_ENDPOINT = "Authenticate"
REST_PRODUCTS_ENDPOINT = "GetInstruments"
REST_GET_L1_ENDPOINT = "GetLevel1"
REST_GET_L2_SNAPSHOT_ENDPOINT = "GetL2Snapshot"
REST_PING_ENDPOINT = "Ping"
REST_ORDER_CREATION_ENDPOINT = "SendOrder"
REST_ORDER_STATUS_ENDPOINT = "GetOrderStatus"
REST_ORDER_CANCELATION_ENDPOINT = "CancelOrder"
REST_ACC_POSITIONS_ENDPOINT = "GetAccountPositions"
REST_TRADE_HISTORY_ENDPOINT = "GetTradesHistory"
_ALL_REST_ENDPOINTS = [
    REST_AUTH_ENDPOINT,
    REST_PRODUCTS_ENDPOINT,
    REST_GET_L1_ENDPOINT,
    REST_GET_L2_SNAPSHOT_ENDPOINT,
    REST_PING_ENDPOINT,
    REST_ORDER_CREATION_ENDPOINT,
    REST_ORDER_STATUS_ENDPOINT,
    REST_ORDER_CANCELATION_ENDPOINT,
    REST_ACC_POSITIONS_ENDPOINT,
    REST_TRADE_HISTORY_ENDPOINT,
]

# ws endpoints
WS_AUTH_ENDPOINT = "AuthenticateUser"
WS_ACC_EVENTS_ENDPOINT = "SubscribeAccountEvents"
WS_TRADES_SUB_ENDPOINT = "SubscribeTrades"
WS_L2_SUB_ENDPOINT = "SubscribeLevel2"
WS_PING_REQUEST = "Ping"
_ALL_WS_ENDPOINTS = [
    WS_AUTH_ENDPOINT,
    WS_ACC_EVENTS_ENDPOINT,
    WS_TRADES_SUB_ENDPOINT,
    WS_L2_SUB_ENDPOINT,
    WS_PING_REQUEST,
]

# ws events
WS_L2_EVENT = "Level2UpdateEvent"
WS_ACC_POS_EVENT = "AccountPositionEvent"
WS_ORDER_STATE_EVENT = "OrderStateEvent"
WS_ORDER_TRADE_EVENT = "OrderTradeEvent"
WS_CANCEL_ORDER_REJECTED_EVENT = "CancelOrderRejectEvent"

# limits
REST_REQ_LIMIT_ID = "WSReqLimitID"
REST_REQ_LIMIT = 5_000
WS_REQ_LIMIT_ID = "WSReqLimitID"
WS_REQ_LIMIT = 500_000

RATE_LIMITS = [
    RateLimit(REST_AUTH_ENDPOINT, limit=5_000, time_interval=60),
    RateLimit(REST_REQ_LIMIT_ID, limit=REST_REQ_LIMIT, time_interval=60),
    RateLimit(WS_AUTH_ENDPOINT, limit=50_000, time_interval=60),
    RateLimit(WS_REQ_LIMIT_ID, limit=WS_REQ_LIMIT, time_interval=60),
]
for e in _ALL_REST_ENDPOINTS:
    RATE_LIMITS.append(  # each limit defined separately so that children can be more granular
        RateLimit(
            limit_id=e,
            limit=REST_REQ_LIMIT,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(limit_id=REST_REQ_LIMIT_ID)],
        )
    )
for e in _ALL_WS_ENDPOINTS:  # noqa: F821
    RATE_LIMITS.append(  # each limit defined separately so that children can be more granular
        RateLimit(
            limit_id=e,
            limit=WS_REQ_LIMIT,
            time_interval=60,
            linked_limits=[LinkedLimitWeightPair(limit_id=WS_REQ_LIMIT_ID)]
        )
    )

# endpoint constant settings
MAX_L2_SNAPSHOT_DEPTH = 400
INCLUDE_LAST_COUNT = 0

# msg types
REQ_MSG_TYPE = 0
RESP_MSG_TYPE = 1
EVENT_MSG_TYPE = 3
ERROR_MSG_TYPE = 5

# time in force types
GTC_TIF = 1

# order types
LIMIT_ORDER_TYPE = 2
ORDER_TYPES = {
    OrderType.LIMIT: LIMIT_ORDER_TYPE
}

# order actions
BUY_ACTION = 0
SELL_ACTION = 1
ORDER_SIDE_MAP = {
    "Buy": TradeType.BUY,
    "Sell": TradeType.SELL,
}

# order state
ACTIVE_ORDER_STATE = "Working"  # can be either OPEN or PARTIALLY_FILLED
CANCELED_ORDER_STATE = "Canceled"
REJECTED_ORDER_STATE = "Rejected"
EXPIRED_ORDER_STATE = "Expired"
FULLY_EXECUTED_ORDER_STATE = "FullyExecuted"
ORDER_STATE_MAP = {
    CANCELED_ORDER_STATE: OrderState.CANCELED,
    REJECTED_ORDER_STATE: OrderState.FAILED,
    EXPIRED_ORDER_STATE: OrderState.FAILED,
    FULLY_EXECUTED_ORDER_STATE: OrderState.FILLED,
}

# fields
OMS_ID_FIELD = "OMSId"
USER_FIELD = "User"
USER_ID_FIELD = "UserId"
USER_NAME_FIELD = "UserName"
ACCOUNT_ID_FIELD = "AccountId"
INSTRUMENT_ID_FIELD = "InstrumentId"
BASE_FIELD = "Product1Symbol"
BASE_ID_FIELD = "Product1"
QUOTE_FIELD = "Product2Symbol"
QUOTE_ID_FIELD = "Product2"
FEE_PRODUCT_ID_FIELD = "FeeProductId"
FEE_AMOUNT_FIELD = "Fee"
START_TIME_FIELD = "StartTime"
TRADE_ID_FIELD = "TradeId"
AUTHENTICATED_FIELD = "Authenticated"
SESSION_TOKEN_FIELD = "SessionToken"
API_KEY_FIELD = "APIKey"
SIGNATURE_FIELD = "Signature"
NONCE_FIELD = "Nonce"
DEPTH_FIELD = "Depth"
INCLUDE_LAST_COUNT_FIELD = "IncludeLastCount"
TIME_IN_FORCE_FIELD = "TimeInForce"
CLIENT_ORDER_ID_FIELD = "ClientOrderId"
CL_ORDER_ID_FIELD = "ClOrderId"  # yes, this and the above are not typos...
ORDER_ID_FIELD = "OrderId"
SIDE_FIELD = "Side"
QUANTITY_FIELD = "quantity"
ORDER_TYPE_FIELD = "OrderType"
LIMIT_PRICE_FIELD = "LimitPrice"
PRICE_FIELD = "Price"
TRADE_TIME_MS_FIELD = "TradeTimeMS"
RESULT_FIELD = "result"
ERROR_CODE_FIELD = "errorcode"
ERROR_MSG_FIELD = "errormsg"
PRODUCT_SYMBOL_FIELD = "ProductSymbol"
SYMBOL_FIELD = "Symbol"
AMOUNT_FIELD = "Amount"
ORIGINAL_QUANTITY_FIELD = "OrigQuantity"
QUANTITY_EXECUTED_FIELD = "QuantityExecuted"
ORDER_STATE_FIELD = "OrderState"
AMOUNT_ON_HOLD_FIELD = "Hold"
ORDER_UPDATE_TS_FIELD = "LastUpdatedTime"
IS_DISABLED_FIELD = "IsDisable"
SESSION_STATUS_FIELD = "SessionStatus"
MIN_QUANT_FIELD = "MinimumQuantity"
MIN_PRICE_INCR_FIELD = "PriceIncrement"
MIN_QUANT_INCR_FIELD = "QuantityIncrement"
RECEIVE_TIME_FIELD = "ReceiveTime"
LAST_TRADED_PRICE_FIELD = "LastTradedPx"
MSG_TYPE_FIELD = "m"
MSG_SEQUENCE_FIELD = "i"
MSG_ENDPOINT_FIELD = "n"
MSG_DATA_FIELD = "o"

TRADE_UPDATE_INSTRUMENT_ID_FIELD = 1
TRADE_UPDATE_AMOUNT_FIELD = 2
TRADE_UPDATE_PRICE_FIELD = 3
TRADE_UPDATE_TS_FIELD = 6
TRADE_UPDATE_SIDE_FIELD = 8

DIFF_UPDATE_TS_FIELD = 2
DIFF_UPDATE_PRICE_FIELD = 6
DIFF_UPDATE_INSTRUMENT_ID_FIELD = 7
DIFF_UPDATE_AMOUNT_FIELD = 8
DIFF_UPDATE_SIDE_FIELD = 9

# other
RESOURCE_NOT_FOUND_ERR_CODE = 104
WS_MESSAGE_TIMEOUT = 20
