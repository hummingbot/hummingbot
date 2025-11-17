from decimal import Decimal
from typing import Dict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "lighter_perpetual"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = None

MARKET_ORDER_SLIPPAGE = Decimal("0.05")

# Maintain the standard Hummingbot naming where DOMAIN represents the default connector alias.
DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = f"{EXCHANGE_NAME}_testnet"
DEFAULT_DOMAIN = DOMAIN

REST_URLS: Dict[str, str] = {
    DOMAIN: "https://mainnet.zklighter.elliot.ai",
    TESTNET_DOMAIN: "https://testnet.zklighter.elliot.ai",
}
REST_URLS["mainnet"] = REST_URLS[DOMAIN]
REST_URLS["testnet"] = REST_URLS[TESTNET_DOMAIN]

WSS_URLS: Dict[str, str] = {
    DOMAIN: "wss://mainnet.zklighter.elliot.ai/stream",
    TESTNET_DOMAIN: "wss://testnet.zklighter.elliot.ai/stream",
}
WSS_URLS["mainnet"] = WSS_URLS[DOMAIN]
WSS_URLS["testnet"] = WSS_URLS[TESTNET_DOMAIN]

SERVER_TIME_PATH_URL = None

PING_URL = "/"
INFO_URL = "/info"
EXCHANGE_STATS_URL = "/api/v1/exchangeStats"
MARKETS_URL = "/api/v1/orderBooks"
EXCHANGE_INFO_URL = MARKETS_URL
TICKER_PRICE_CHANGE_URL = MARKETS_URL
ORDERBOOK_SNAPSHOT_URL = "/api/v1/orderBookOrders"
RECENT_TRADES_URL = "/api/v1/recentTrades"
TRADES_URL = "/api/v1/trades"
ACCOUNT_ACTIVE_ORDERS_URL = "/api/v1/accountActiveOrders"
ACCOUNT_INACTIVE_ORDERS_URL = "/api/v1/accountInactiveOrders"
ACCOUNT_ALL_URL = "/api/v1/account"
ACCOUNT_INFO_URL = ACCOUNT_ALL_URL
ORDER_URL = "/api/v1/orders"
POSITION_INFORMATION_URL = "/api/v1/positions"
ACCOUNT_TRADE_LIST_URL = "/api/v1/trades"
CREATE_ORDER_URL = "/api/v1/sendTx"
CANCEL_ORDER_URL = "/api/v1/sendTx"
SET_LEVERAGE_URL = "/api/v1/sendTx"
GET_LAST_FUNDING_RATE_PATH_URL = "/api/v1/fundings"
FUNDING_PAYMENT_URL = "/api/v1/funding_payments"
SEND_TX_URL = "/api/v1/sendTx"
SEND_TX_BATCH_URL = "/api/v1/sendTxBatch"
NEXT_NONCE_URL = "/api/v1/nextNonce"
TRANSFER_FEE_INFO_URL = "/api/v1/transferFeeInfo"
WITHDRAWAL_DELAY_URL = "/api/v1/withdrawalDelay"

FUNDING_RATE_UPDATE_INTERNAL_SECOND = 60
CURRENCY = "USD"

META_INFO = "meta"
ASSET_CONTEXT_TYPE = "metaAndAssetCtxs"
TRADES_TYPE = "userFills"
ORDER_STATUS_TYPE = "orderStatus"
USER_STATE_TYPE = "clearinghouseState"

TRADES_ENDPOINT_NAME = "trades"
DEPTH_ENDPOINT_NAME = "order_book"
USER_ORDERS_ENDPOINT_NAME = "orderUpdates"
USEREVENT_ENDPOINT_NAME = "user"

PUBLIC_WS_ORDER_BOOK_CHANNEL = "order_book:{market_id}"
PUBLIC_WS_TRADES_CHANNEL = "trade:{market_id}"
PUBLIC_WS_MARKET_STATS_CHANNEL = "market_stats:{market_id}"
PRIVATE_WS_ACCOUNT_ALL_CHANNEL = "account_all/{account_index}"
PRIVATE_WS_ACCOUNT_ALL_ORDERS_CHANNEL = "account_all_orders/{account_index}"
PRIVATE_WS_ACCOUNT_ALL_TRADES_CHANNEL = "account_all_trades/{account_index}"
PRIVATE_WS_ACCOUNT_ALL_POSITIONS_CHANNEL = "account_all_positions/{account_index}"
PRIVATE_WS_ACCOUNT_MARKET_CHANNEL = "account_market/{market_id}/{account_index}"
WS_TRANSACTION_CHANNEL = "transaction"
WS_EXECUTED_TRANSACTION_CHANNEL = "executed_transaction"

ORDER_STATE = {
    "ACTIVE": OrderState.OPEN,
    "active": OrderState.OPEN,
    "PENDING": OrderState.OPEN,
    "pending": OrderState.OPEN,
    "RESTING": OrderState.OPEN,
    "resting": OrderState.OPEN,
    "OPEN": OrderState.OPEN,
    "open": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "filled": OrderState.FILLED,
    "EXECUTED": OrderState.FILLED,
    "executed": OrderState.FILLED,
    "CANCELED": OrderState.CANCELED,
    "CANCELLED": OrderState.CANCELED,
    "canceled": OrderState.CANCELED,
    "cancelled": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "rejected": OrderState.FAILED,
    "FAILED": OrderState.FAILED,
    "failed": OrderState.FAILED,
}

HEARTBEAT_TIME_INTERVAL = 30.0

REST_GLOBAL_LIMIT_ID = "lighter_rest_global_limit"
REST_GLOBAL_LIMIT = 24_000
RATE_LIMIT_INTERVAL = 60

ENDPOINT_WEIGHTS = {
    SEND_TX_URL: 6,
    SEND_TX_BATCH_URL: 6,
    NEXT_NONCE_URL: 6,
    PING_URL: 100,
    INFO_URL: 100,
    "/api/v1/publicPools": 50,
    "/api/v1/txFromL1TxHash": 50,
    "/api/v1/candlesticks": 50,
    ACCOUNT_INACTIVE_ORDERS_URL: 100,
    "/api/v1/deposit/latest": 100,
    "/api/v1/pnl": 100,
    "/api/v1/apikeys": 150,
    ACCOUNT_ACTIVE_ORDERS_URL: 300,
    ACCOUNT_ALL_URL: 300,
    ORDER_URL: 300,
    TRADES_URL: 300,
    RECENT_TRADES_URL: 300,
    MARKETS_URL: 300,
    ORDERBOOK_SNAPSHOT_URL: 300,
    EXCHANGE_STATS_URL: 300,
    TRANSFER_FEE_INFO_URL: 300,
    WITHDRAWAL_DELAY_URL: 300,
    POSITION_INFORMATION_URL: 300,
    GET_LAST_FUNDING_RATE_PATH_URL: 300,
    FUNDING_PAYMENT_URL: 300,
}

RATE_LIMITS = [
    RateLimit(
        REST_GLOBAL_LIMIT_ID, limit=REST_GLOBAL_LIMIT, time_interval=RATE_LIMIT_INTERVAL
    ),
]

for endpoint, weight in ENDPOINT_WEIGHTS.items():
    per_route_limit = max(1, REST_GLOBAL_LIMIT // weight)
    RATE_LIMITS.append(
        RateLimit(
            limit_id=endpoint,
            limit=per_route_limit,
            time_interval=RATE_LIMIT_INTERVAL,
            linked_limits=[LinkedLimitWeightPair(REST_GLOBAL_LIMIT_ID, weight=weight)],
        )
    )

ORDER_NOT_EXIST_MESSAGE = "order"
UNKNOWN_ORDER_MESSAGE = "Order not found or already closed"
