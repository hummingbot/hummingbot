# A single source of truth for constant variables related to the exchange

EXCHANGE_NAME = "bybit_perpetual"

REST_URLS = {"bybit_perpetual_main": "https://api.bybit.com/",
             "bybit_perpetual_testnet": "https://api-testnet.bybit.com/"}
WSS_NON_LINEAR_PUBLIC_URLS = {"bybit_perpetual_main": "wss://stream.bybit.com/realtime",
                              "bybit_perpetual_testnet": "wss://stream-testnet.bybit.com/realtime"}
WSS_NON_LINEAR_PRIVATE_URLS = WSS_NON_LINEAR_PUBLIC_URLS
WSS_LINEAR_PUBLIC_URLS = {"bybit_perpetual_main": "wss://stream.bybit.com/realtime_public",
                          "bybit_perpetual_testnet": "wss://stream-testnet.bybit.com/realtime_public"}
WSS_LINEAR_PRIVATE_URLS = {"bybit_perpetual_main": "wss://stream.bybit.com/realtime_private",
                           "bybit_perpetual_testnet": "wss://stream-testnet.bybit.com/realtime_private"}

REST_API_VERSION = "v2"

HBOT_BROKER_ID = "HBOT"

# REST API Public Endpoints
LINEAR_MARKET = "linear"
NON_LINEAR_MARKET = "non_linear"

LATEST_SYMBOL_INFORMATION_ENDPOINT = {
    LINEAR_MARKET: f"{REST_API_VERSION}/public/tickers",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/public/tickers"}
QUERY_SYMBOL_ENDPOINT = {
    LINEAR_MARKET: f"{REST_API_VERSION}/public/symbols",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/public/symbols"}
ORDER_BOOK_ENDPOINT = {
    LINEAR_MARKET: f"{REST_API_VERSION}/public/orderBook/L2",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/public/orderBook/L2"}
SERVER_TIME_PATH_URL = {
    LINEAR_MARKET: f"{REST_API_VERSION}/public/time",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/public/time"
}

# REST API Private Endpoints
SET_LEVERAGE_PATH_URL = {
    LINEAR_MARKET: "private/linear/position/set-leverage",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/position/leverage/save"}
GET_LAST_FUNDING_RATE_PATH_URL = {
    LINEAR_MARKET: "private/linear/funding/prev-funding",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/funding/prev-funding"}
GET_POSITIONS_PATH_URL = {
    LINEAR_MARKET: "private/linear/position/list",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/position/list"}
PLACE_ACTIVE_ORDER_PATH_URL = {
    LINEAR_MARKET: "private/linear/order/create",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/order/create"}
CANCEL_ACTIVE_ORDER_PATH_URL = {
    LINEAR_MARKET: "private/linear/order/cancel",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/order/cancel"}
QUERY_ACTIVE_ORDER_PATH_URL = {
    LINEAR_MARKET: "private/linear/order/search",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/order"}
USER_TRADE_RECORDS_PATH_URL = {
    LINEAR_MARKET: "private/linear/trade/execution/list",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/execution/list"}
GET_WALLET_BALANCE_PATH_URL = {
    LINEAR_MARKET: f"{REST_API_VERSION}/private/wallet/balance",
    NON_LINEAR_MARKET: f"{REST_API_VERSION}/private/wallet/balance"}

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
WS_SUBSCRIPTION_EXECUTIONS_ENDPOINT_NAME = "execution"

GET_LIMIT_ID = "GETLimit"
POST_LIMIT_ID = "POSTLimit"
GET_RATE = 49  # per second
POST_RATE = 19  # per second

NON_LINEAR_PRIVATE_BUCKET_100_LIMIT_ID = "NonLinearPrivateBucket100"
NON_LINEAR_PRIVATE_BUCKET_600_LIMIT_ID = "NonLinearPrivateBucket600"
NON_LINEAR_PRIVATE_BUCKET_75_LIMIT_ID = "NonLinearPrivateBucket75"
NON_LINEAR_PRIVATE_BUCKET_120_B_LIMIT_ID = "NonLinearPrivateBucket120B"
NON_LINEAR_PRIVATE_BUCKET_120_C_LIMIT_ID = "NonLinearPrivateBucket120C"

LINEAR_PRIVATE_BUCKET_100_LIMIT_ID = "LinearPrivateBucket100"
LINEAR_PRIVATE_BUCKET_600_LIMIT_ID = "LinearPrivateBucket600"
LINEAR_PRIVATE_BUCKET_75_LIMIT_ID = "LinearPrivateBucket75"
LINEAR_PRIVATE_BUCKET_120_A_LIMIT_ID = "LinearPrivateBucket120A"

# Request error codes
ORDER_NOT_EXISTS_ERROR_CODE = 130010
