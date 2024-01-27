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

SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 25
WS_PING_REQUEST = "ping"
WS_PONG_RESPONSE = "pong"

# API ORDER BOOK DATA SOURCE CHANNELS
WS_TRADES_CHANNEL = "trades"
WS_TRADES_ALL_CHANNEL = "trades-all"
WS_MARK_PRICE_CHANNEL = "mark-price"
WS_INDEX_TICKERS_CHANNEL = "index-tickers"
WS_FUNDING_INFO_CHANNEL = "funding-rate"
WS_ORDER_BOOK_400_DEPTH_100_MS_EVENTS_CHANNEL = "books"
WS_ORDER_BOOK_5_DEPTH_100_MS_EVENTS_CHANNEL = "books5"
WS_ORDER_BOOK_1_DEPTH_10_MS_EVENTS_CHANNEL = "bbo-tbt"
WS_INSTRUMENTS_INFO_CHANNEL = "instruments"

# USER STREAM DATA SOURCE CHANNELS
WS_POSITIONS_CHANNEL = "positions"
WS_ORDERS_CHANNEL = "orders"
WS_ACCOUNT_CHANNEL = "account"
# -------------------------------------------
# WEB UTILS ENDPOINTS
# The structure is REST_url = {method: GET/POST, endpoint: /api/v5/...} since for the same endpoint you can have
# different methods. This is also useful for rate limit ids.
# -------------------------------------------
GET = "GET"
POST = "POST"
METHOD = "METHOD"
ENDPOINT = "ENDPOINT"

# REST API Public Endpoints
REST_LATEST_SYMBOL_INFORMATION = {METHOD: GET,
                                  ENDPOINT: f"/api/{REST_API_VERSION}/market/tickers"}
REST_ORDER_BOOK = {METHOD: GET,
                   ENDPOINT: f"/api/{REST_API_VERSION}/market/books"}
REST_SERVER_TIME = {METHOD: GET,
                    ENDPOINT: f"/api/{REST_API_VERSION}/public/time"}
REST_MARK_PRICE = {METHOD: GET,
                   ENDPOINT: f"/api/{REST_API_VERSION}/public/mark-price"}
REST_INDEX_TICKERS = {METHOD: GET,
                      ENDPOINT: f"/api/{REST_API_VERSION}/public/index-tickers"}

# REST API Private General Endpoints
REST_GET_WALLET_BALANCE = {METHOD: GET,
                           ENDPOINT: f"/api/{REST_API_VERSION}/account/balance"}
REST_SET_POSITION_MODE = {METHOD: POST,
                          ENDPOINT: f"/api/{REST_API_VERSION}/account/set-position-mode"}

# REST API Private Pair Specific Endpoints
REST_SET_LEVERAGE = {METHOD: POST,
                     ENDPOINT: f"/api/{REST_API_VERSION}/account/set-leverage"}
REST_FUNDING_RATE_INFO = {METHOD: GET,
                          ENDPOINT: f"/api/{REST_API_VERSION}/public/funding-rate"}
REST_GET_POSITIONS = {METHOD: GET,
                      ENDPOINT: f"/api/{REST_API_VERSION}/account/positions"}
REST_PLACE_ACTIVE_ORDER = {METHOD: POST,
                           ENDPOINT: f"/api/{REST_API_VERSION}/trade/order"}
REST_CANCEL_ACTIVE_ORDER = {METHOD: POST,
                            ENDPOINT: f"/api/{REST_API_VERSION}/trade/cancel-order"}
REST_QUERY_ACTIVE_ORDER = {METHOD: GET,
                           ENDPOINT: REST_PLACE_ACTIVE_ORDER[ENDPOINT]}
REST_USER_TRADE_RECORDS = {METHOD: GET,
                           ENDPOINT: f"/api/{REST_API_VERSION}/trade/fills"}