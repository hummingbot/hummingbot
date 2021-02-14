# A single source of truth for constant variables related to the exchange

EXCHANGE_NAME = "probit"

REST_URL = "https://api.probit.com/api/exchange/"
WSS_URL = "wss://api.probit.com/api/exchange/v1/ws"

API_VERSON = "v1"

TICKER_PATH_URL = f"{REST_URL+API_VERSON}/ticker"
MARKETS_PATH_URL = f"{REST_URL+API_VERSON}/market"
ORDER_BOOK_PATH_URL = f"{REST_URL+API_VERSON}/order_book"
NEW_ORDER_PATH_URL = f"{REST_URL+API_VERSON}/new_order"
