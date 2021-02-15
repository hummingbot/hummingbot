# A single source of truth for constant variables related to the exchange

EXCHANGE_NAME = "probit"

REST_URL = "https://api.probit.com/api/exchange/"
WSS_URL = "wss://api.probit.com/api/exchange/v1/ws"

REST_API_VERSON = "v1"

# REST API Public Endpoints
TICKER_URL = f"{REST_URL+REST_API_VERSON}/ticker"
MARKETS_URL = f"{REST_URL+REST_API_VERSON}/market"
ORDER_BOOK_URL = f"{REST_URL+REST_API_VERSON}/order_book"
NEW_ORDER_URL = f"{REST_URL+REST_API_VERSON}/new_order"

# REST API Private Endpoints
NEW_ORDER_URL = f"{REST_URL+REST_API_VERSON}/new_order"
CANCEL_ORDER_URL = f"{REST_URL+REST_API_VERSON}/cancel_order"
ORDER_HISTORY_URL = f"{REST_URL+REST_API_VERSON}/order_history"
TRADE_HISTORY_URL = f"{REST_URL+REST_API_VERSON}/trade_history"
BALANCE_URL = f"{REST_URL+REST_API_VERSON}/balance"
ORDER_URL = f"{REST_URL+REST_API_VERSON}/order"
OPEN_ORDER_URL = f"{REST_URL+REST_API_VERSON}/open_order"

# Order Status Definitions
ORDER_STATUS = [
    "open",
    "filled",
    "cancelled",
]
