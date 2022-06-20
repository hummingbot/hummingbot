# A single source of truth for constant variables related to the exchange
# TODO: Include this in place of the other stuff...
EXCHANGE_NAME = "coinex"

REST_URL = "https://api.coinex.com/"
WSS_URL = "wss://socket.coinex.com/"

REST_API_VERSON = "v1"

# REST API Public Endpoints
# TIME_URL = f"{REST_URL+REST_API_VERSON}/time"
# TICKER_URL = f"{REST_URL+REST_API_VERSON}/market/ticker"
TICKER_URL = f"{REST_URL+REST_API_VERSON}/market/deals"
MARKETS_URL = f"{REST_URL+REST_API_VERSON}/market/info"
ORDER_BOOK_URL = f"{REST_URL+REST_API_VERSON}/market/depth"

# REST API Private Endpoints
NEW_LIMIT_ORDER_URL = f"{REST_URL+REST_API_VERSON}/order/limit"
NEW_MARKET_ORDER_URL = f"{REST_URL+REST_API_VERSON}/order/market"
CANCEL_ORDER_URL = f"{REST_URL+REST_API_VERSON}/order/pending"
ORDER_HISTORY_URL = f"{REST_URL+REST_API_VERSON}/order/finished"
TRADE_HISTORY_URL = f"{REST_URL+REST_API_VERSON}/order/user/deals"
BALANCE_URL = f"{REST_URL+REST_API_VERSON}/balance/info"
ORDER_URL = f"{REST_URL+REST_API_VERSON}/order/status"
OPEN_ORDER_URL = f"{REST_URL+REST_API_VERSON}/order/pending"

# Websocket Private Channels
WS_PRIVATE_CHANNELS = [
    "server.sign",
    "order.subscribe",
    "asset.subscribe"
]

# Order Status Definitions
ORDER_STATUS = [
    "not_deal",
    "part_deal",
    "done",
]

TYPE_OPEN = "open"
TYPE_CHANGE = "change"
TYPE_MATCH = "match"
TYPE_DONE = "done"
SIDE_BUY = "buy"
SIDE_SELL = "sell"

ERROR_CODES = {
    "1": "Error",
    "2": "Parameter error",
    "3": "Internal error",
    "25": "Signature error",
    "35": "Service unavailable",
    "36": "Service timeout",
    "40": "Main and sub accounts unpaired",
    "49": "Transfer to sub account rejected",
    "107": "Insufficient balance",
    "115": "forbid trading",
    "227": "tonce check error, correct tonce should be within one minute of the current time",
    "600": "Order number does not exist",
    "601": "Other user's order",
    "602": "Below min. buy/sell limit",
    "606": "Order price and the latest price deviation is too large",
    "651": "Merge depth error"
}
