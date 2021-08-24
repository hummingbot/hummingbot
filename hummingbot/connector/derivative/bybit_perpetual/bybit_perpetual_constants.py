# A single source of truth for constant variables related to the exchange

EXCHANGE_NAME = "bybit perpetual"

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
GET_LAST_FUNDING_RATE_PATH_URL = "/private/funding/prev-funding"
GET_POSITIONS_PATH_URL = "/private/position/list"

# Funding Settlement Time Span
FUNDING_SETTLEMENT_DURATION = (5, 5)  # seconds before snapshot, seconds after snapshot

# WebSocket Public Endpoints
WS_PING_REQUEST = "ping"
WS_ORDER_BOOK_EVENTS_TOPIC = "orderBook_200.100ms"
WS_TRADES_TOPIC = "trade"
WS_INSTRUMENTS_INFO_TOPIC = "instrument_info.100ms"

WS_AUTHENTICATE_USER_ENDPOINT_NAME = "auth"
WS_SUBSCRIPTION_POSITIONS_ENDPOINT_NAME = "position"
WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME = "order"
WS_SUBSCRIPTION_STOP_ORDERS_ENDPOINT_NAME = "stop_order"
