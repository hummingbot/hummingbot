from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

# DEFAULT_DOMAIN = "co"
DEFAULT_DOMAIN = ""

# Base URL
REST_URL = "https://localhost.{}/"

PUBLIC_API_VERSION = "v0"
PRIVATE_API_VERSION = "v0"

# Public API endpoints or BinanceClient function
TICKER_PRICE_CHANGE_PATH_URL = "/historical-prices/tap-tools/{asset}" # _get_last_traded_price # TODO rename to HISTORIC_PRICES
# TICKER_BOOK_PATH_URL = "/ticker/bookTicker" # get_all_pairs_prices # Is this required? Not included in api requirements
EXCHANGE_INFO_PATH_URL = "/markets" # trading_rules_request_path, trading_pairs_request_path # Rules are optional
PING_PATH_URL = "/settings" # check_network_request_path
SNAPSHOT_PATH_URL = "/order-books/{market-id}" # _request_order_book_snapshot # order book is not aggregated
#SERVER_TIME_PATH_URL = "/time" # get_current_server_time # Server time is optional

# Private API endpoints or BinanceClient function
ACCOUNTS_PATH_URL = "/balances/{address}" # _update_balances
# MY_TRADES_PATH_URL = "/myTrades" # _update_order_fills_from_trades # _all_trade_updates_for_order # trades history is optional
ORDER_PATH_URL = "/orders/details" # _place_order # _place_cancel # _request_order_status

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS = "ORDERS"
ORDERS_24HR = "ORDERS_24HR"
RAW_REQUESTS = "RAW_REQUESTS"

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 5000

RATE_LIMITS = [
    # Pools
    RateLimit(limit_id=REQUEST_WEIGHT, limit=6000, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS, limit=50, time_interval=10 * ONE_SECOND),
    RateLimit(limit_id=ORDERS_24HR, limit=160000, time_interval=ONE_DAY),
    RateLimit(limit_id=RAW_REQUESTS, limit=61000, time_interval= 5 * ONE_MINUTE),
    # Weighted Limits
    RateLimit(limit_id=TICKER_PRICE_CHANGE_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 2),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 20),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 100),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=PING_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 20),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    RateLimit(limit_id=ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 4),
                             LinkedLimitWeightPair(ORDERS, 1),
                             LinkedLimitWeightPair(ORDERS_24HR, 1),
                             LinkedLimitWeightPair(RAW_REQUESTS, 1)])
]
