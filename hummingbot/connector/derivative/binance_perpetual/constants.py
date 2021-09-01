from hummingbot.core.api_throttler.data_types import RateLimit

EXCHANGE_NAME = "binance_perpetual"

PERPETUAL_BASE_URL = "https://fapi.binance.com/fapi/"
TESTNET_BASE_URL = "https://testnet.binancefuture.com/fapi/"

PERPETUAL_WS_URL = "wss://fstream.binance.com/"
TESTNET_WS_URL = "wss://stream.binancefuture.com/"

PUBLIC_WS_ENDPOINT = "stream"
PRIVATE_WS_ENDPOINT = "ws"

API_VERSION = "v1"

# Public API Endpoints
SNAPSHOT_REST_URL = "/depth"
TICKER_PRICE_URL = "/ticker/bookTicker"
TICKER_PRICE_CHANGE_URL = "/ticker/24hr"
EXCHANGE_INFO_URL = "/exchangeInfo"
RECENT_TRADES_URL = "/trades"

# Private API Endpoints
BINANCE_USER_STREAM_ENDPOINT = "/listenKey"

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS_1MIN = "ORDERS_1MIN"
ORDERS_1SEC = "ORDERS_1SEC"

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 2400

RATE_LIMITS = [
    RateLimit(limit_id=REQUEST_WEIGHT, limit=2400, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS_1MIN, limit=1200, time_interval=ONE_MINUTE),
    RateLimit(limit_id=REQUEST_WEIGHT, limit=300, time_interval=10),
    RateLimit(limit_id=BINANCE_USER_STREAM_ENDPOINT, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[REQUEST_WEIGHT]),
]
