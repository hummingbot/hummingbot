from hummingbot.core.api_throttler.data_types import RateLimit

HBOT_ORDER_ID_PREFIX = "latoken-hbot-"
MAX_ORDER_ID_LEN = 36
SNAPSHOT_LIMIT_SIZE = 100
DEFAULT_DOMAIN = "com"
DOMAIN_TO_ENDPOINT = {DEFAULT_DOMAIN: "api.latoken"}

# Base URL
REST_URL = "https://{}.{}"
WSS_URL = "wss://{}.{}/stomp"

# API versions
REST_API_VERSION = "/v2"
WSS_API_VERSION = "/v1"

# Public API endpoints or LatokenClient function
TICKER_PATH_URL = "/ticker"
CURRENCY_PATH_URL = "/currency"
PAIR_PATH_URL = "/pair"
PING_PATH_URL = "/time"
BOOK_PATH_URL = "/book"
SNAPSHOT_PATH_URL = "/depth"

# Private API endpoints or LatokenClient function
ACCOUNTS_PATH_URL = "/auth/account"
TRADES_FOR_PAIR_PATH_URL = "/auth/trade/pair"
ORDER_PLACE_PATH_URL = "/auth/order/place"
ORDER_CANCEL_PATH_URL = "/auth/order/cancel"
GET_ORDER_PATH_URL = "/auth/order/getOrder"
USER_ID_PATH_URL = "/auth/user"
FEES_PATH_URL = "/auth/trade/fee"

# Latoken params
SIDE_BUY = 'BUY'
SIDE_SELL = 'SELL'

TIME_IN_FORCE_GTC = 'GTC'  # Good till cancelled
TIME_IN_FORCE_IOC = 'IOC'  # Immediate or cancel
TIME_IN_FORCE_FOK = 'FOK'  # Fill or kill

# WS (streams)
# Public
BOOK_STREAM = WSS_API_VERSION + '/book/{symbol}'
TRADES_STREAM = WSS_API_VERSION + '/trade/{symbol}'
CURRENCIES_STREAM = WSS_API_VERSION + '/currency'  # All available currencies
PAIRS_STREAM = WSS_API_VERSION + '/pair'  # All available pairs
TICKER_ALL_STREAM = WSS_API_VERSION + '/ticker'
TICKERS_PAIR_STREAM = WSS_API_VERSION + '/ticker/{base}/{quote}'
RATES_STREAM = WSS_API_VERSION + '/rate/{base}/{quote}'
RATES_QUOTE_STREAM = WSS_API_VERSION + '/rate/{quote}'

# Private
ORDERS_STREAM = '/user/{user}' + WSS_API_VERSION + '/order'
TRADE_UPDATE_STREAM = '/user/{user}' + WSS_API_VERSION + '/trade'
ACCOUNTS_STREAM = '/user/{user}' + WSS_API_VERSION + '/account/total'  # Returns all accounts of a user including empty ones
ACCOUNT_STREAM = '/user/{user}' + WSS_API_VERSION + '/account'
TRANSACTIONS_STREAM = '/user/{user}' + WSS_API_VERSION + '/transaction'  # Returns external transactions (deposits and withdrawals)
TRANSFERS_STREAM = '/user/{user}' + WSS_API_VERSION + '/transfers'  # Returns internal transfers on the platform (inter_user, ...)

# Time intervals in seconds
PER_TRADE_UPDATE_LIMIT = 10
ONE_SECOND = 1
ONE_MINUTE = 60 * ONE_SECOND
ONE_HOUR = 60 * ONE_MINUTE
ONE_DAY = 24 * ONE_HOUR
TWELVE_HOURS = 12 * ONE_HOUR
THIRTY_MINUTES = 30 * ONE_MINUTE
LISTEN_KEY_KEEP_ALIVE_INTERVAL = float(THIRTY_MINUTES)
SHORT_POLL_INTERVAL = 5.0
UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
LONG_POLL_INTERVAL = 2.0 * ONE_MINUTE
WS_HEARTBEAT_TIME_INTERVAL = 30
UPDATE_TRADE_UPDATE_INTERVAL = .5

MAX_REQUEST = 5000
MAX_ALLOWED_TPS = 100

# Websocket event types
DIFF_EVENT_TYPE = "b"
TRADE_EVENT_TYPE = "t"

SUBSCRIPTION_ID_ACCOUNT = 0
SUBSCRIPTION_ID_BOOKS = 1
SUBSCRIPTION_ID_TRADES = 2
SUBSCRIPTION_ID_ORDERS = 3
SUBSCRIPTION_ID_TRADE_UPDATE = 2

GLOBAL_RATE_LIMIT = "global"

RATE_LIMITS = [
    RateLimit(limit_id=GLOBAL_RATE_LIMIT, limit=MAX_ALLOWED_TPS, time_interval=ONE_SECOND),
]
# Rate Limit Type
# REQUEST_WEIGHT = "REQUEST_WEIGHT"
# ORDERS = "ORDERS"
# ORDERS_24HR = "ORDERS_24HR"
