# A SINGLE POINT OF TRUTH FOR BITTREX

from hummingbot.core.api_throttler.data_types import RateLimit

EXCHANGE_NAME = "Bittrex"
PING_TIMEOUT = 10.0
MAX_RETRIES = 20
MESSAGE_TIMEOUT = 30.0
SNAPSHOT_TIMEOUT = 10.0
NaN = float("nan")

BITTREX_REST_URL = "https://api.bittrex.com/v3"
BITTREX_WS_URL = "https://socket-v3.bittrex.com/signalr"

# WEBSOCKET CHANNEl KEYS
TRADE_EVENT_KEY = "trade"
DIFF_EVENT_KEY = "orderbook_25"

# SERVER REFERENCE DATA URLS
SERVER_TIME_URL = "/ping"

# SERVER UTILITY URLS
ORDERBOOK_SNAPSHOT_URL = "/markets/{}/orderbook"

BITTREX_EXCHANGE_INFO_PATH = "/markets"
BITTREX_MARKET_SUMMARY_PATH = "/markets/summaries"
BITTREX_TICKER_PATH = "/markets/tickers"


ORDERBOOK_SNAPSHOT_LIMIT_ID = "orderBook"
RATE_LIMITS = [
    RateLimit(limit_id=ORDERBOOK_SNAPSHOT_LIMIT_ID, limit=60, time_interval=60),
    RateLimit(limit_id=SERVER_TIME_URL, limit=60, time_interval=60),

]
