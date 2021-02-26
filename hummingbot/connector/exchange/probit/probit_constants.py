# A single source of truth for constant variables related to the exchange

EXCHANGE_NAME = "probit"

REST_URL = "https://api.probit.{}/api/exchange/"
WSS_URL = "wss://api.probit.{}/api/exchange/v1/ws"

REST_API_VERSON = "v1"

# REST API Public Endpoints
TIME_URL = f"{REST_URL+REST_API_VERSON}/time"
TICKER_URL = f"{REST_URL+REST_API_VERSON}/ticker"
MARKETS_URL = f"{REST_URL+REST_API_VERSON}/market"
ORDER_BOOK_URL = f"{REST_URL+REST_API_VERSON}/order_book"
TOKEN_URL = "https://accounts.probit.{}/token"

# REST API Private Endpoints
NEW_ORDER_URL = f"{REST_URL+REST_API_VERSON}/new_order"
CANCEL_ORDER_URL = f"{REST_URL+REST_API_VERSON}/cancel_order"
ORDER_HISTORY_URL = f"{REST_URL+REST_API_VERSON}/order_history"
TRADE_HISTORY_URL = f"{REST_URL+REST_API_VERSON}/trade_history"
BALANCE_URL = f"{REST_URL+REST_API_VERSON}/balance"
ORDER_URL = f"{REST_URL+REST_API_VERSON}/order"
OPEN_ORDER_URL = f"{REST_URL+REST_API_VERSON}/open_order"

# Websocket Private Channels
WS_PRIVATE_CHANNELS = [
    "open_order",
    "order_history",
    "trade_history",
    "balance"
]

# Order Status Definitions
ORDER_STATUS = [
    "open",
    "filled",
    "cancelled",
]
