# Init connector
EXCHANGE_NAME = "okx_perpetual"
REST_API_VERSION = "v5"

# Initial constants
DEFAULT_DOMAIN = EXCHANGE_NAME
AWS_DOMAIN = "okx_perpetual_aws"
DEMO_DOMAIN = "okx_perpetual_demo"

REST_URLS = {DEFAULT_DOMAIN: "https://www.okx.com",
             AWS_DOMAIN: "https://aws.okx.com",
             DEMO_DOMAIN: "https://www.okx.com"}

# -------------------------------------------
# WEB SOCKET ENDPOINTS
# -------------------------------------------
WSS_PUBLIC_URLS = {DEFAULT_DOMAIN: f"wss://ws.okx.com:8443/ws/{REST_API_VERSION}/public",
                   AWS_DOMAIN: f"wss://wsaws.okx.com:8443/ws/{REST_API_VERSION}/public",
                   DEMO_DOMAIN: f"wss://wspap.okx.com:8443/ws/{REST_API_VERSION}/public?brokerId=9999"}

WSS_PRIVATE_URLS = {DEFAULT_DOMAIN: f"wss://ws.okx.com:8443/ws/{REST_API_VERSION}/private",
                    AWS_DOMAIN: f"wss://wsaws.okx.com:8443/ws/{REST_API_VERSION}/private",
                    DEMO_DOMAIN: f"wss://wspap.okx.com:8443/ws/{REST_API_VERSION}/private?brokerId=9999"}

WSS_BUSINESS_URLS = {DEFAULT_DOMAIN: f"wss://ws.okx.com:8443/ws/{REST_API_VERSION}/business",
                     AWS_DOMAIN: f"wss://wsaws.okx.com:8443/ws/{REST_API_VERSION}/business",
                     DEMO_DOMAIN: f"wss://wspap.okx.com:8443/ws/{REST_API_VERSION}/business?brokerId=9999"}

SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 30
WS_PING_REQUEST = "ping"
WS_PONG_RESPONSE = "pong"
WS_TRADES_CHANNEL = "trades"
WS_TRADES_ALL_CHANNEL = "trades-all"
WS_ORDER_BOOK_400_DEPTH_100_MS_EVENTS_CHANNEL = "books"
WS_ORDER_BOOK_5_DEPTH_100_MS_EVENTS_CHANNEL = "books5"
WS_ORDER_BOOK_1_DEPTH_10_MS_EVENTS_CHANNEL = "bbo-tbt"
WS_INSTRUMENTS_INFO_CHANNEL = "instruments"
# -------------------------------------------
# WEB UTILS ENDPOINTS
# -------------------------------------------
# REST API Public Endpoints
LATEST_SYMBOL_INFORMATION_ENDPOINT = f"/api/{REST_API_VERSION}/market/tickers"
# TODO: Fill QUERY_SYMBOL_ENDPOINT with the correct endpoint, if necessary
# QUERY_SYMBOL_ENDPOINT = f""
ORDER_BOOK_ENDPOINT = f"/api/{REST_API_VERSION}/market/books"
SERVER_TIME_PATH_URL = f"/api/{REST_API_VERSION}/public/time"
MARK_PRICE_PATH_URL = f"/api/{REST_API_VERSION}/public/mark-price"
INDEX_TICKERS_PATH_URL = f"/api/{REST_API_VERSION}/public/index-tickers"

# REST API Private General Endpoints
GET_WALLET_BALANCE_PATH_URL = f"/api/{REST_API_VERSION}/account/balance"
SET_POSITION_MODE_URL = f"/api/{REST_API_VERSION}/account/set-position-mode"

# REST API Private Pair Specific Endpoints
SET_LEVERAGE_PATH_URL = f"/api/{REST_API_VERSION}/account/set-leverage"
FUNDING_RATE_INFO_PATH_URL = f"/api/{REST_API_VERSION}/public/funding-rate"
GET_POSITIONS_PATH_URL = f"/api/{REST_API_VERSION}/account/positions"
PLACE_ACTIVE_ORDER_PATH_URL = f"/api/{REST_API_VERSION}/trade/order"
CANCEL_ACTIVE_ORDER_PATH_URL = f"/api/{REST_API_VERSION}/trade/cancel-order"
# TODO: Check if search active order is the same as query active order but switching REST/POST
QUERY_ACTIVE_ORDER_PATH_URL = PLACE_ACTIVE_ORDER_PATH_URL
USER_TRADE_RECORDS_PATH_URL = f"/api/{REST_API_VERSION}/trade/fills"
