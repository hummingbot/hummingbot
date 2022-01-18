# A single source of truth for constant variables related to the exchange

EXCHANGE_NAME = "huobi"

REST_URL = "https://api.huobi.pro"
WS_PUBLIC_URL = "wss://api.huobi.pro/ws"
WS_PRIVATE_URL = "wss://api.huobi.pro/ws/v2"


SYMBOLS_URL = "/common/symbols"
TICKER_URL = "/market/tickers"
DEPTH_URL = "/market/depth"

API_VERSION = "/v1"

SERVER_TIME_URL = "/common/timestamp"
ACCOUNT_ID_URL = "/account/accounts"
ACCOUNT_BALANCE_URL = "/account/accounts/{}/balance"
ORDER_DETAIL_URL = "/order/orders/{}"
PLACE_ORDER_URL = "/order/orders/place"
CANCEL_ORDER_URL = "/order/orders/{}/submitcancel"
BATCH_CANCEL_URL = "/order/orders/batchcancel"

HUOBI_ACCOUNT_UPDATE_TOPIC = "accounts.update#2"
HUOBI_ORDER_UPDATE_TOPIC = "orders#*"
HUOBI_TRADE_DETAILS_TOPIC = "trade.clearing#*"

HUOBI_SUBSCRIBE_TOPICS = {HUOBI_ORDER_UPDATE_TOPIC, HUOBI_ACCOUNT_UPDATE_TOPIC, HUOBI_TRADE_DETAILS_TOPIC}
