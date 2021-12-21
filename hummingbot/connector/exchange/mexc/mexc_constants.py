from hummingbot.core.api_throttler.data_types import RateLimit, LinkedLimitWeightPair

EXCHANGE_NAME = "mexc"
# URLs

MEXC_BASE_URL = "https://www.mexc.com"

MEXC_SYMBOL_URL = '/open/api/v2/market/symbols'
MEXC_TICKERS_URL = '/open/api/v2/market/ticker'
MEXC_DEPTH_URL = '/open/api/v2/market/depth?symbol={trading_pair}&depth=200'
MEXC_PRICE_URL = '/open/api/v2/market/ticker?symbol={trading_pair}'
MEXC_PING_URL = '/open/api/v2/common/ping'


MEXC_PLACE_ORDER = "/open/api/v2/order/place"
MEXC_ORDER_DETAILS_URL = '/open/api/v2/order/query'
MEXC_ORDER_CANCEL = '/open/api/v2/order/cancel'
MEXC_BATCH_ORDER_CANCEL = '/open/api/v2/order/cancel'
MEXC_BALANCE_URL = '/open/api/v2/account/info'
MEXC_DEAL_DETAIL = '/open/api/v2/order/deal_detail'

# WS
MEXC_WS_URL_PUBLIC = 'wss://wbs.mexc.com/raw/ws'

MINUTE = 1
SECOND_MINUTE = 2
HTTP_ENDPOINTS_LIMIT_ID = "AllHTTP"
HTTP_LIMIT = 20
WS_AUTH_LIMIT_ID = "AllWsAuth"
WS_ENDPOINTS_LIMIT_ID = "AllWs"
WS_LIMIT = 20

RATE_LIMITS = [
    RateLimit(
        limit_id=HTTP_ENDPOINTS_LIMIT_ID,
        limit=HTTP_LIMIT,
        time_interval=MINUTE
    ),
    # public http
    RateLimit(
        limit_id=MEXC_SYMBOL_URL,
        limit=HTTP_LIMIT,
        time_interval=SECOND_MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=MEXC_TICKERS_URL,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=MEXC_DEPTH_URL,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    # private http
    RateLimit(
        limit_id=MEXC_PRICE_URL,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=MEXC_PING_URL,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=MEXC_PLACE_ORDER,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=MEXC_ORDER_DETAILS_URL,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=MEXC_ORDER_CANCEL,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=MEXC_BATCH_ORDER_CANCEL,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=MEXC_BALANCE_URL,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    RateLimit(
        limit_id=MEXC_DEAL_DETAIL,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    # ws public
    RateLimit(limit_id=WS_AUTH_LIMIT_ID, limit=50, time_interval=MINUTE),
    RateLimit(limit_id=WS_ENDPOINTS_LIMIT_ID, limit=WS_LIMIT, time_interval=MINUTE),
    RateLimit(
        limit_id=MEXC_WS_URL_PUBLIC,
        limit=WS_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(WS_ENDPOINTS_LIMIT_ID)],
    ),

]
