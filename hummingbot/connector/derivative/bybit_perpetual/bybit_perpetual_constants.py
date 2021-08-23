# A single source of truth for constant variables related to the exchange

EXCHANGE_NAME = "bybit"

REST_URLS = {"bybit_main": "https://api.bybit.com/",
             "bybit_testnet": "https://api-testnet.bybit.com/"}
WSS_URLS = {"bybit_main": "wss://stream.bybit.com/realtime",
            "bybit_testnet": "wss://stream-testnet.bybit.com/realtime"}

REST_API_VERSION = "v2"

# REST API Public Endpoints
LATEST_SYMBOL_INFORMATION_ENDPOINT = "/public/tickers"
QUERY_SYMBOL_ENDPOINT = "/public/symbols"

# REST API Private Endpoints
ORDER_BOOK_ENDPOINT = "/public/orderBook/L2"
GET_FUNDING_FEE_PATH_URL = "/private/linear/funding/prev-funding"
SET_LEVERAGE_PATH_URL = "/private/position/leverage/save"
GET_LAST_FUNDING_RATE = "/private/funding/prev-funding"

# WebSocket Public Endpoints
WS_PING_REQUEST = "ping"
WS_ORDER_BOOK_EVENTS_TOPIC = "orderBook_200.100ms"
WS_TRADES_TOPIC = "trade"
WS_INSTRUMENTS_INFO_TOPIC = "instrument_info.100ms"

# WebSocket Message Events
