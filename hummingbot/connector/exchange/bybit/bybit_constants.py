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


# WebSocket Public Endpoints
WS_PING_REQUEST = "ping"
WS_ORDER_BOOK_EVENTS_TOPIC = "orderBook_200.100ms"
WS_TRADES_TOPIC = "trade"
WS_INSTRUMENTS_INFO_TOPIC = "instrument_info.100ms"

# WebSocket Message Events
