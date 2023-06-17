import sys

from hummingbot.connector.constants import SECOND
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "polkadex"

MAX_ID_LEN = 32
CLIENT_ID_PREFIX = "HBOT"

DEFAULT_DOMAIN = ""
TESTNET_DOMAIN = "testnet"

GRAPHQL_ENDPOINTS = {
    DEFAULT_DOMAIN: "https://gu5xqmhhcnfeveotzwhe6ohfba.appsync-api.eu-central-1.amazonaws.com/graphql",
    TESTNET_DOMAIN: "https://kckpespz5bb2rmdnuxycz6e7he.appsync-api.eu-central-1.amazonaws.com/graphql",
}
BLOCKCHAIN_URLS = {
    DEFAULT_DOMAIN: "wss://mainnet.polkadex.trade",
    TESTNET_DOMAIN: "wss://blockchain.polkadex.trade",
}
POLKADEX_SS58_PREFIX = 88

ORDERBOOK_UPDATES_STREAM_NAME = "ob-inc"
RECENT_TRADES_STREAM_NAME = "recent-trades"

# Rate limit IDs
ORDERBOOK_LIMIT_ID = "Orderbook"
ALL_ASSETS_LIMIT_ID = "AllAssets"
ALL_MARKETS_LIMIT_ID = "AllMarkets"
FIND_USER_LIMIT_ID = "FindUser"
PUBLIC_TRADES_LIMIT_ID = "RecentTrades"
ALL_BALANCES_LIMIT_ID = "AllBalances"
PLACE_ORDER_LIMIT_ID = "PlaceOrder"
CANCEL_ORDER_LIMIT_ID = "CancelOrder"
BATCH_ORDER_UPDATES_LIMIT_ID = "BatchOrderUpdates"
ORDER_UPDATE_LIMIT_ID = "OrderUpdate"

NO_LIMIT = sys.maxsize

RATE_LIMITS = [
    RateLimit(
        limit_id=ALL_ASSETS_LIMIT_ID,
        limit=NO_LIMIT,
        time_interval=SECOND,
    ),
    RateLimit(
        limit_id=ALL_MARKETS_LIMIT_ID,
        limit=NO_LIMIT,
        time_interval=SECOND,
    ),
    RateLimit(
        limit_id=ORDERBOOK_LIMIT_ID,
        limit=NO_LIMIT,
        time_interval=SECOND,
    ),
    RateLimit(
        limit_id=FIND_USER_LIMIT_ID,
        limit=NO_LIMIT,
        time_interval=SECOND,
    ),
    RateLimit(
        limit_id=PUBLIC_TRADES_LIMIT_ID,
        limit=NO_LIMIT,
        time_interval=SECOND,
    ),
    RateLimit(
        limit_id=ALL_BALANCES_LIMIT_ID,
        limit=NO_LIMIT,
        time_interval=SECOND,
    ),
    RateLimit(
        limit_id=PLACE_ORDER_LIMIT_ID,
        limit=NO_LIMIT,
        time_interval=SECOND,
    ),
    RateLimit(
        limit_id=CANCEL_ORDER_LIMIT_ID,
        limit=NO_LIMIT,
        time_interval=SECOND,
    ),
    RateLimit(
        limit_id=BATCH_ORDER_UPDATES_LIMIT_ID,
        limit=NO_LIMIT,
        time_interval=SECOND,
    ),
    RateLimit(
        limit_id=ORDER_UPDATE_LIMIT_ID,
        limit=NO_LIMIT,
        time_interval=SECOND,
    ),
]


ORDER_STATE = {
    "OPEN": OrderState.OPEN,
    "CANCELLED": OrderState.CANCELED,
    "CLOSED": OrderState.FILLED,
}


CUSTOM_TYPES = {
    "runtime_id": 1,
    "versioning": [],
    "types": {
        "OrderPayload": {
            "type": "struct",
            "type_mapping": [
                ["client_order_id", "H256"],
                ["user", "AccountId"],
                ["main_account", "AccountId"],
                ["pair", "String"],
                ["side", "OrderSide"],
                ["order_type", "OrderType"],
                ["quote_order_quantity", "String"],
                ["qty", "String"],
                ["price", "String"],
                ["timestamp", "i64"],
            ],
        },
        "CancelOrderPayload": {"type": "struct", "type_mapping": [["id", "String"]]},
        "TradingPair": {
            "type": "struct",
            "type_mapping": [
                ["base_asset", "AssetId"],
                ["quote_asset", "AssetId"],
            ],
        },
        "OrderSide": {
            "type": "enum",
            "type_mapping": [
                ["Ask", "Null"],
                ["Bid", "Null"],
            ],
        },
        "AssetId": {
            "type": "enum",
            "type_mapping": [
                ["asset", "u128"],
                ["polkadex", "Null"],
            ],
        },
        "OrderType": {
            "type": "enum",
            "type_mapping": [
                ["LIMIT", "Null"],
                ["MARKET", "Null"],
            ],
        },
        "EcdsaSignature": "[u8; 65]",
        "Ed25519Signature": "H512",
        "Sr25519Signature": "H512",
        "AnySignature": "H512",
        "MultiSignature": {
            "type": "enum",
            "type_mapping": [
                ["Ed25519", "Ed25519Signature"],
                ["Sr25519", "Sr25519Signature"],
                ["Ecdsa", "EcdsaSignature"],
            ],
        },
    },
}

ORDER_NOT_FOUND_ERROR_CODE = "-32000"
ORDER_NOT_FOUND_MESSAGE = "Order not found"
