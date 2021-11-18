# A single source of truth for constant variables related to the exchange

EXCHANGE_NAME = "huobi"

REST_URL = "https://api.huobi.pro"
WS_PUBLIC_URL = "wss://api.huobi.pro/ws"
WS_PRIVATE_URL = "wss://api.huobi.pro/ws/v2"


SYMBOLS_URL = "/v1/common/symbols"
TICKER_URL = "/market/tickers"
DEPTH_URL = "/market/depth"

HUOBI_ACCOUNT_UPDATE_TOPIC = "accounts.update#2"
HUOBI_ORDER_UPDATE_TOPIC = "orders#*"
