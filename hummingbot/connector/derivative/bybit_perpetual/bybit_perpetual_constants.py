# A single source of truth for constant variables related to the exchange

EXCHANGE_NAME = "bybit_perpetual"

REST_URLS = {"bybit_perpetual_main": "https://api.bybit.com/",
             "bybit_perpetual_testnet": "https://api-testnet.bybit.com/"}
WSS_URLS = {"bybit_perpetual_main": "wss://stream.bybit.com/realtime",
            "bybit_perpetual_testnet": "wss://stream-testnet.bybit.com/realtime",
            "bybit_perpetual_main_private": "wss://stream.bybit.com/realtime_private",
            "bybit_perpetual_testnet_private": "wss://stream-testnet.bybit.com/realtime_private"}

REST_API_VERSION = "v2"

# REST API Public Endpoints
LATEST_SYMBOL_INFORMATION_ENDPOINT = {
    "linear": f"{REST_API_VERSION}/public/tickers",
    "non_linear": f"{REST_API_VERSION}/public/tickers"}
QUERY_SYMBOL_ENDPOINT = {
    "linear": f"{REST_API_VERSION}/public/symbols",
    "non_linear": f"{REST_API_VERSION}/public/symbols"}
ORDER_BOOK_ENDPOINT = {
    "linear": f"{REST_API_VERSION}/public/orderBook/L2",
    "non_linear": f"{REST_API_VERSION}/public/orderBook/L2"}

# REST API Private Endpoints
SET_LEVERAGE_PATH_URL = {
    "linear": "private/linear/position/set-leverage",
    "non_linear": f"{REST_API_VERSION}/private/position/leverage/save"}
GET_LAST_FUNDING_RATE_PATH_URL = {
    "linear": "private/linear/funding/prev-funding",
    "non_linear": f"{REST_API_VERSION}/private/funding/prev-funding"}
GET_POSITIONS_PATH_URL = {
    "linear": "private/linear/position/list",
    "non_linear": f"{REST_API_VERSION}/private/position/list"}
PLACE_ACTIVE_ORDER_PATH_URL = {
    "linear": "private/linear/order/create",
    "non_linear": f"{REST_API_VERSION}/private/order/create"}
CANCEL_ACTIVE_ORDER_PATH_URL = {
    "linear": "private/linear/order/cancel",
    "non_linear": f"{REST_API_VERSION}/private/order/cancel"}
QUERY_ACTIVE_ORDER_PATH_URL = {
    "linear": "private/linear/order/search",
    "non_linear": f"{REST_API_VERSION}/private/order"}
USER_TRADE_RECORDS_PATH_URL = {
    "linear": "private/linear/trade/execution/list",
    "non_linear": f"{REST_API_VERSION}/private/execution/list"}
GET_WALLET_BALANCE_PATH_URL = {
    "linear": f"{REST_API_VERSION}/private/wallet/balance",
    "non_linear": f"{REST_API_VERSION}/private/wallet/balance"}

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
