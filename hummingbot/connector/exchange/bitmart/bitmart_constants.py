# A single source of truth for constant variables related to the exchange

from hummingbot.core.api_throttler.data_types import RateLimit

EXCHANGE_NAME = "bitmart"
REST_URL = "https://api-cloud.bitmart.com"
REST_URL_HK = "https://api-cloud.bitmart.news"
WSS_URL = "wss://ws-manager-compress.bitmart.com?protocol=1.1"
WSS_URL_HK = "wss://ws-manager-compress.bitmart.news?protocol=1.1"

# REST API ENDPOINTS
CHECK_NETWORK_PATH_URL = "system/service"
GET_TRADING_PAIRS_PATH_URL = "spot/v1/symbols"
GET_TRADING_RULES_PATH_URL = "spot/v1/symbols/details"
GET_LAST_TRADING_PRICES_PATH_URL = "spot/v1/ticker"
GET_ORDER_BOOK_PATH_URL = "spot/v1/symbols/book"
CREATE_ORDER_PATH_URL = "spot/v1/submit_order"
CANCEL_ORDER_PATH_URL = "spot/v2/cancel_order"
GET_ACCOUNT_SUMMARY_PATH_URL = "spot/v1/wallet"
GET_ORDER_DETAIL_PATH_URL = "spot/v1/order_detail"
GET_TRADE_DETAIL_PATH_URL = "spot/v1/trades"
GET_OPEN_ORDERS_PATH_URL = "spot/v1/orders"

# WS API ENDPOINTS
WS_CONNECT = "WSConnect"
WS_SUBSCRIBE = "WSSubscribe"

# BitMart has a per method API limit
RATE_LIMITS = [
    RateLimit(limit_id=CHECK_NETWORK_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=GET_TRADING_PAIRS_PATH_URL, limit=5, time_interval=1),
    RateLimit(limit_id=GET_TRADING_RULES_PATH_URL, limit=5, time_interval=1),
    RateLimit(limit_id=GET_LAST_TRADING_PRICES_PATH_URL, limit=5, time_interval=1),
    RateLimit(limit_id=GET_ORDER_BOOK_PATH_URL, limit=5, time_interval=1),
    RateLimit(limit_id=CREATE_ORDER_PATH_URL, limit=50, time_interval=1),
    RateLimit(limit_id=CANCEL_ORDER_PATH_URL, limit=50, time_interval=1),
    RateLimit(limit_id=GET_ACCOUNT_SUMMARY_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=GET_ORDER_DETAIL_PATH_URL, limit=50, time_interval=1),
    RateLimit(limit_id=GET_TRADE_DETAIL_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=GET_OPEN_ORDERS_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=WS_CONNECT, limit=1, time_interval=1),
    RateLimit(limit_id=WS_SUBSCRIBE, limit=60, time_interval=600),
]

ORDER_STATUS = {
    1: "FAILED",        # Order failure
    2: "OPEN",          # Placing order
    3: "REJECTED",      # Order failure, Freeze failure
    4: "ACTIVE",        # Order success, Pending for fulfilment
    5: "ACTIVE",        # Partially filled
    6: "FILLED",        # Fully filled
    7: "ACTIVE",        # Canceling
    8: "CANCELED",      # Canceled
    9: "ACTIVE",        # Outstanding (4 and 5)
    10: "COMPLETED"     # 6 and 8
}
