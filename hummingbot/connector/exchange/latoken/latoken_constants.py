from hummingbot.connector.constants import MINUTE, TWELVE_HOURS
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

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
SNAPSHOT_PATH_URL = "/book"

# Private API endpoints or LatokenClient function
ACCOUNTS_PATH_URL = "/auth/account"
TRADES_FOR_PAIR_PATH_URL = "/auth/trade/pair"
ORDER_PATH_URL = "/auth/order/place"
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

WS_CONNECT_MSG = "CONNECT"

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
SECOND = 1
HOUR = 60 * MINUTE
LISTEN_KEY_KEEP_ALIVE_INTERVAL = float(TWELVE_HOURS)
UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0 * SECOND
WS_HEARTBEAT_TIME_INTERVAL = 30 * SECOND

GENERAL_TPS = 700
MAX_ALLOWED_TPS = 3500

SUBSCRIPTION_ID_BOOKS = 0
SUBSCRIPTION_ID_TRADES = 1
SUBSCRIPTION_ID_ACCOUNT = 2
SUBSCRIPTION_ID_ORDERS = 3
SUBSCRIPTION_ID_TRADE_UPDATE = 4

PUBLIC_LIMIT_ID = "PublicPoints"
PRIVATE_LIMIT_ID = "PrivatePoints"  # includes place-orders
PUBLIC_LINKED_LIMITS = [LinkedLimitWeightPair(PUBLIC_LIMIT_ID)]
PRIVATE_LINKED_LIMITS = [LinkedLimitWeightPair(PRIVATE_LIMIT_ID)]

RATE_LIMITS = [
    RateLimit(limit_id=PUBLIC_LIMIT_ID, limit=GENERAL_TPS, time_interval=SECOND),
    RateLimit(limit_id=PRIVATE_LIMIT_ID, limit=GENERAL_TPS, time_interval=SECOND),
    # Public API
    RateLimit(limit_id=TICKER_PATH_URL, limit=GENERAL_TPS, time_interval=SECOND, linked_limits=PUBLIC_LINKED_LIMITS),
    RateLimit(limit_id=CURRENCY_PATH_URL, limit=GENERAL_TPS, time_interval=SECOND, linked_limits=PUBLIC_LINKED_LIMITS),
    RateLimit(limit_id=PAIR_PATH_URL, limit=GENERAL_TPS, time_interval=SECOND, linked_limits=PUBLIC_LINKED_LIMITS),
    RateLimit(limit_id=PING_PATH_URL, limit=GENERAL_TPS, time_interval=SECOND, linked_limits=PUBLIC_LINKED_LIMITS),
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=GENERAL_TPS, time_interval=SECOND, linked_limits=PUBLIC_LINKED_LIMITS),
    # Private API
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=GENERAL_TPS, time_interval=SECOND, linked_limits=PRIVATE_LINKED_LIMITS),
    RateLimit(limit_id=TRADES_FOR_PAIR_PATH_URL, limit=GENERAL_TPS, time_interval=SECOND, linked_limits=PRIVATE_LINKED_LIMITS),
    RateLimit(limit_id=ORDER_PATH_URL, limit=GENERAL_TPS, time_interval=SECOND, linked_limits=PRIVATE_LINKED_LIMITS),
    RateLimit(limit_id=ORDER_CANCEL_PATH_URL, limit=MAX_ALLOWED_TPS, time_interval=SECOND, linked_limits=PRIVATE_LINKED_LIMITS),
    RateLimit(limit_id=GET_ORDER_PATH_URL, limit=GENERAL_TPS, time_interval=SECOND, linked_limits=PRIVATE_LINKED_LIMITS),
    RateLimit(limit_id=USER_ID_PATH_URL, limit=GENERAL_TPS, time_interval=SECOND, linked_limits=PRIVATE_LINKED_LIMITS),
    RateLimit(limit_id=FEES_PATH_URL, limit=GENERAL_TPS, time_interval=SECOND, linked_limits=PRIVATE_LINKED_LIMITS),
]
