# A single source of truth for constant variables related to the exchange

EXCHANGE_NAME = "bybit_perpetual"

REST_URLS = {"bybit_perpetual_main": "https://api.bybit.com/",
             "bybit_perpetual_testnet": "https://api-testnet.bybit.com/"}
WSS_URLS = {"bybit_perpetual_main": "wss://stream.bybit.com/realtime",
            "bybit_perpetual_testnet": "wss://stream-testnet.bybit.com/realtime"}

REST_API_VERSION = "v2"

# REST API Public Endpoints
LATEST_SYMBOL_INFORMATION_ENDPOINT = "/public/tickers"
QUERY_SYMBOL_ENDPOINT = "/public/symbols"
ORDER_BOOK_ENDPOINT = "/public/orderBook/L2"
GET_WALLET_BALANCE_ENDPOINT = "/private/wallet/balance"

# REST API Private Endpoints
GET_FUNDING_FEE_PATH_URL = "/private/linear/funding/prev-funding"
SET_LEVERAGE_PATH_URL = "/private/position/leverage/save"
GET_LAST_FUNDING_RATE_PATH_URL = "/private/funding/prev-funding"
GET_POSITIONS_PATH_URL = "/private/position/list"
PLACE_ACTIVE_ORDER_ENDPOINT = "/private/order/create"
CANCEL_ACTIVE_ORDER_ENDPOINT = "/private/order/cancel"
QUERY_ACTIVE_ORDER_ENDPOINT = "/private/order"
USER_TRADE_RECORDS_ENDPOINT = "/private/execution/list"

# Funding Settlement Time Span
FUNDING_SETTLEMENT_DURATION = (5, 5)  # seconds before snapshot, seconds after snapshot

# WebSocket Public Endpoints
WS_PING_REQUEST = "ping"
WS_ORDER_BOOK_EVENTS_TOPIC = "orderBook_200.100ms"
WS_TRADES_TOPIC = "trade"
WS_INSTRUMENTS_INFO_TOPIC = "instrument_info.100ms"

# WebSocket Message Events
