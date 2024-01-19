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

WSS_PUBLIC_URLS = {DEFAULT_DOMAIN: f"wss://ws.okx.com:8443/ws/{REST_API_VERSION}/public",
                   AWS_DOMAIN: f"wss://wsaws.okx.com:8443/ws/{REST_API_VERSION}/public",
                   DEMO_DOMAIN: f"wss://wspap.okx.com:8443/ws/{REST_API_VERSION}/public?brokerId=9999"}

WSS_PRIVATE_URLS = {DEFAULT_DOMAIN: f"wss://ws.okx.com:8443/ws/{REST_API_VERSION}/private",
                    AWS_DOMAIN: f"wss://wsaws.okx.com:8443/ws/{REST_API_VERSION}/private",
                    DEMO_DOMAIN: f"wss://wspap.okx.com:8443/ws/{REST_API_VERSION}/private?brokerId=9999"}

WSS_BUSINESS_URLS = {DEFAULT_DOMAIN: f"wss://ws.okx.com:8443/ws/{REST_API_VERSION}/business",
                     AWS_DOMAIN: f"wss://wsaws.okx.com:8443/ws/{REST_API_VERSION}/business",
                     DEMO_DOMAIN: f"wss://wspap.okx.com:8443/ws/{REST_API_VERSION}/business?brokerId=9999"}


# -------------------------------------------
# WEB UTILS ENDPOINTS
# -------------------------------------------
# REST API Public Endpoints
LATEST_SYMBOL_INFORMATION_ENDPOINT = f"/api/{REST_API_VERSION}/market/tickers"
# TODO: Fill QUERY_SYMBOL_ENDPOINT with the correct endpoint, if necessary
# QUERY_SYMBOL_ENDPOINT = f""
ORDER_BOOK_ENDPOINT = f"/api/{REST_API_VERSION}/market/books"
SERVER_TIME_PATH_URL = f"/api/{REST_API_VERSION}/public/time"

# REST API Private General Endpoints
GET_WALLET_BALANCE_PATH_URL = f"/api/{REST_API_VERSION}/account/balance"
SET_POSITION_MODE_URL = f"/api/{REST_API_VERSION}/account/set-position-mode"

# REST API Private Pair Specific Endpoints
SET_LEVERAGE_PATH_URL = f"/api/{REST_API_VERSION}/account/set-leverage"
GET_FUNDING_RATE = f"/api/{REST_API_VERSION}/public/funding-rate"
GET_POSITIONS_PATH_URL = f"/api/{REST_API_VERSION}/account/positions"
PLACE_ACTIVE_ORDER_PATH_URL = f"/api/{REST_API_VERSION}/trade/order"
CANCEL_ACTIVE_ORDER_PATH_URL = f"/api/{REST_API_VERSION}/trade/cancel-order"
# TODO: Check if search active order is the same as query active order but switching REST/POST
QUERY_ACTIVE_ORDER_PATH_URL = PLACE_ACTIVE_ORDER_PATH_URL
USER_TRADE_RECORDS_PATH_URL = f"/api/{REST_API_VERSION}/trade/fills"
