# hummingbot/connector/exchange/zaif/zaif_constants.py

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

# デフォルトドメイン
DEFAULT_DOMAIN = "jp"

# Hummingbot の注文IDプレフィックスと最大長
HBOT_ORDER_ID_PREFIX = "x-ZAIFEXCHNG"
MAX_ORDER_ID_LEN = 32
# Base URLs
PUBLIC_API_BASE_URL = "https://api.zaif.jp/api/1"
PRIVATE_API_BASE_URL = "https://api.zaif.jp/tapi"
PRIVATE_API_PATH_URL = "/tapi"
# API Endpoints
PRIVATE_API_ENDPOINT = ""  # 追加
# エンドポイントパス
SYMBOLS_PATH_URL = "/currency_pairs/all"
SERVER_TIME_PATH_URL = "/time"  # ZaifのAPIドキュメントに合わせて修正
ALL_TICKERS_PATH_URL = "/ticker/all"
GET_ORDERS_PATH_URL = "/active_orders"
ORDER_PLACE_PATH_URL = "/trade"
ORDER_CANCEL_PATH_URL = "/cancel_order"
BALANCE_PATH_URL = "/get_info"
TRADE_HISTORY_PATH_URL = "/trade_history"

# Websocket イベントタイプ（ZaifがWebSocketをサポートしていない場合は削除）
DEPTH_UPDATE_EVENT_TYPE = "depthUpdate"
TRADE_EVENT_TYPE = "trade"

# API パラメータ
SIDE_BUY = "bid"
SIDE_SELL = "ask"

TIME_IN_FORCE_GTC = "gtc"  # Good till cancelled
TIME_IN_FORCE_IOC = "ioc"  # Immediate or cancel
TIME_IN_FORCE_FOK = "fok"  # Fill or kill

# レートリミットタイプ
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS = "ORDERS"
ORDERS_24HR = "ORDERS_24HR"
RAW_REQUESTS = "RAW_REQUESTS"

# レートリミット時間間隔（秒）
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 5000

# 注文ステータスのマッピング
ORDER_STATE = {
    "pending": OrderState.PENDING_CREATE,
    "open": OrderState.OPEN,
    "closed": OrderState.FILLED,
    "canceled": OrderState.CANCELED,
    # Zaifの注文ステータスに合わせて追加・修正
}

# レートリミットの設定
RATE_LIMITS = [
    # パブリックAPI
    RateLimit(limit_id="public_api", limit=300, time_interval=ONE_MINUTE),
    # プライベートAPI
    RateLimit(limit_id="private_api", limit=100, time_interval=ONE_MINUTE),
    # 必要に応じて他のレートリミットを追加
]

# デフォルトのレートリミットID
DEFAULT_LIMIT_ID = "public_api"
PUBLIC_API_LIMIT_ID = "public_api"
PRIVATE_API_LIMIT_ID = "private_api"
CHECK_NETWORK_LIMIT_ID = "public_api"

# エラーコードとメッセージ
ORDER_NOT_EXIST_ERROR_CODE = -2013
ORDER_NOT_EXIST_MESSAGE = "Order does not exist"
UNKNOWN_ORDER_ERROR_CODE = -2011
UNKNOWN_ORDER_MESSAGE = "Unknown order sent"

# その他のZaif API特有の定数
CURRENCY_PAIRS = [
    "btc_jpy",
    "eth_jpy",
    "xrp_jpy",
    # 必要に応じて追加
]

BASE_ASSETS = [
    "btc",
    "eth",
    "xrp",
    # 必要に応じて追加
]

QUOTE_ASSETS = [
    "jpy",
    # 他の通貨ペアがある場合は追加
]

# Zaif が WebSocket プライベートチャンネルをサポートしている場合（サポートしていない場合は削除）
PRIVATE_WALLET_CHANNEL = "private_wallet_channel_name"  # 実際のチャンネル名に置き換え

