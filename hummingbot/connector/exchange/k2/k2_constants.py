# A single source of truth for constant variables related to the exchange

EXCHANGE_NAME = "k2"
REST_URL = "https://api-q2.fourwordsalluppercase.com/"
WSS_URL = "ws://18.135.217.229:8184/v1"

REST_API_VERSION = "v1"
WS_API_VERSION = "v2"

WSS_MY_TRADES = "SubscribeMyTrades"
WSS_ORDER_BOOK = "SubscribeOrderBook"
WSS_TRADES = "SubscribeTrades"
WSS_LOGIN = "Login"

# REST API Public Endpoints
GET_TRADING_PAIRS = f"{REST_API_VERSION}/Public/GetPairs"
GET_TRADING_PAIRS_STATS = f"{REST_API_VERSION}/Public/GetPairStats"
GET_MARKET = f"{REST_API_VERSION}/Public/Market"
GET_ORDER_BOOK = f"{REST_API_VERSION}/Public/GetOrderBook"
GET_PUBLIC_TRADE_HISTORY = f"{REST_API_VERSION}/Public/GetTradeHistory"

# REST API Private Endpoints
GET_BALANCES = f"{REST_API_VERSION}/Private/GetBalances"
GET_DETAILED_BALANCES = f"{REST_API_VERSION}/Private/GetDetailedBalances"
GET_OPEN_ORDERS = f"{REST_API_VERSION}/Private/GetOpenOrders"
GET_ORDERS = f"{REST_API_VERSION}/Private/GetOrders"
GET_PRIVATE_TRADE_HISTORY = f"{REST_API_VERSION}/Private/GetTradeHistory"
PLACE_ORDER = f"{REST_API_VERSION}/Private/PlaceOrders"
MOVE_ORDER = f"{REST_API_VERSION}/Private/MoveOrders"
CANCEL_ORDER = f"{REST_API_VERSION}/Private/CancelOrder"
CANCEL_ALL_ORDERS = f"{REST_API_VERSION}/Private/CancelAllOrders"

# Order Status Defintions
ORDER_STATUS = [
    'New',
    'Partially Filled',
    'Filled',
    'Expired',
    'Cancelled',
    'Canceling',
    'Processing',
    'No Balance',
    'No Fill'
]
