# A single source of truth for constant variables related to the exchange
from itertools import chain

from hummingbot.core.api_throttler.data_types import RateLimit

EXCHANGE_NAME = "bybit_perpetual"

REST_URLS = {"bybit_perpetual_main": "https://api.bybit.com/",
             "bybit_perpetual_testnet": "https://api-testnet.bybit.com/"}
WSS_URLS = {"bybit_perpetual_main": "wss://stream.bybit.com/realtime",
            "bybit_perpetual_testnet": "wss://stream-testnet.bybit.com/realtime"}

REST_API_VERSION = "v2"

# REST API Public Endpoints
LATEST_SYMBOL_INFORMATION_ENDPOINT = {
    "linear": f"{REST_API_VERSION}/public/tickers",
    "non_linear": f"{REST_API_VERSION}/public/tickers"}
LATEST_SYMBOL_INFORMATION_ENDPOINT_GET_LIMIT_ID = f"{LATEST_SYMBOL_INFORMATION_ENDPOINT}-GET"
QUERY_SYMBOL_ENDPOINT = {
    "linear": f"{REST_API_VERSION}/public/symbols",
    "non_linear": f"{REST_API_VERSION}/public/symbols"}
QUERY_SYMBOL_ENDPOINT_GET_LIMIT_ID = f"{QUERY_SYMBOL_ENDPOINT}-GET"
ORDER_BOOK_ENDPOINT = {
    "linear": f"{REST_API_VERSION}/public/orderBook/L2",
    "non_linear": f"{REST_API_VERSION}/public/orderBook/L2"}
ORDER_BOOK_ENDPOINT_GET_LIMIT_ID = f"{ORDER_BOOK_ENDPOINT}-GET"

# REST API Private Endpoints
SET_LEVERAGE_PATH_URL = {
    "linear": "private/linear/position/set-leverage",
    "non_linear": f"{REST_API_VERSION}/private/position/leverage/save"}
GET_LAST_FUNDING_RATE_PATH_URL = {
    "linear": "private/linear/funding/prev-funding",
    "non_linear": f"{REST_API_VERSION}/private/funding/prev-funding"}
GET_POSITIONS_PATH_URL = {
    "linear": "private/linear/position/list",
    "non_linear": f"{REST_API_VERSION}/private/position/list"}
PLACE_ACTIVE_ORDER_PATH_URL = {
    "linear": "private/linear/order/create",
    "non_linear": f"{REST_API_VERSION}/private/order/create"}
CANCEL_ACTIVE_ORDER_PATH_URL = {
    "linear": "private/linear/order/cancel",
    "non_linear": f"{REST_API_VERSION}/private/order/cancel"}
QUERY_ACTIVE_ORDER_PATH_URL = {
    "linear": "private/linear/order/search",
    "non_linear": f"{REST_API_VERSION}/private/order"}
USER_TRADE_RECORDS_PATH_URL = {
    "linear": "private/linear/trade/execution/list",
    "non_linear": f"{REST_API_VERSION}/private/execution/list"}
GET_WALLET_BALANCE_PATH_URL = {
    "linear": f"{REST_API_VERSION}/private/wallet/balance",
    "non_linear": f"{REST_API_VERSION}/private/wallet/balance"}

# Funding Settlement Time Span
FUNDING_SETTLEMENT_DURATION = (5, 5)  # seconds before snapshot, seconds after snapshot

# WebSocket Public Endpoints
WS_PING_REQUEST = "ping"
WS_ORDER_BOOK_EVENTS_TOPIC = "orderBook_200.100ms"
WS_TRADES_TOPIC = "trade"
WS_INSTRUMENTS_INFO_TOPIC = "instrument_info.100ms"
WS_AUTHENTICATE_USER_ENDPOINT_NAME = "auth"
WS_SUBSCRIPTION_POSITIONS_ENDPOINT_NAME = "position"
WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME = "order"
WS_SUBSCRIPTION_EXECUTIONS_ENDPOINT_NAME = "execution"

PUBLIC_LOW_FI_GET_LIMIT_ID = "PublicLowFiGET"
PUBLIC_LOW_FI_POST_LIMIT_ID = "PublicLowFiPOST"
MAX_PUBLIC_RATE = 50 * 60 * 2
MAX_PUBLIC_INTERVAL = 60 * 2
_PUBLIC_RATE_LIMITS = [
    RateLimit(limit_id=PUBLIC_LOW_FI_GET_LIMIT_ID, limit=50, time_interval=1),
    RateLimit(limit_id=PUBLIC_LOW_FI_POST_LIMIT_ID, limit=20, time_interval=1),
    RateLimit(
        limit_id=LATEST_SYMBOL_INFORMATION_ENDPOINT_GET_LIMIT_ID,
        limit=MAX_PUBLIC_RATE,
        time_interval=MAX_PUBLIC_INTERVAL,
        linked_limits=[PUBLIC_LOW_FI_GET_LIMIT_ID],
    ),
    RateLimit(
        limit_id=QUERY_SYMBOL_ENDPOINT_GET_LIMIT_ID,
        limit=MAX_PUBLIC_RATE,
        time_interval=MAX_PUBLIC_INTERVAL,
        linked_limits=[PUBLIC_LOW_FI_GET_LIMIT_ID],
    ),
    RateLimit(
        limit_id=ORDER_BOOK_ENDPOINT_GET_LIMIT_ID,
        limit=MAX_PUBLIC_RATE,
        time_interval=MAX_PUBLIC_INTERVAL,
        linked_limits=[PUBLIC_LOW_FI_GET_LIMIT_ID],
    ),
]

NON_LINEAR_PRIVATE_BUCKET_100_LIMIT_ID = "NonLinearPrivate100"
NON_LINEAR_PRIVATE_BUCKET_600_LIMIT_ID = "NonLinearPrivate600"
NON_LINEAR_PRIVATE_BUCKET_75_LIMIT_ID = "NonLinearPrivate75"
NON_LINEAR_PRIVATE_BUCKET_120_A_LIMIT_ID = "NonLinearPrivate120A"
NON_LINEAR_PRIVATE_BUCKET_120_B_LIMIT_ID = "NonLinearPrivate120B"
_NON_LINEAR_PRIVATE_RATE_LIMITS = [
    RateLimit(limit_id=NON_LINEAR_PRIVATE_BUCKET_100_LIMIT_ID, limit=100, time_interval=60),
    RateLimit(limit_id=NON_LINEAR_PRIVATE_BUCKET_600_LIMIT_ID, limit=600, time_interval=60),
    RateLimit(limit_id=NON_LINEAR_PRIVATE_BUCKET_75_LIMIT_ID, limit=75, time_interval=60),
    RateLimit(limit_id=NON_LINEAR_PRIVATE_BUCKET_120_A_LIMIT_ID, limit=120, time_interval=60),
    RateLimit(limit_id=NON_LINEAR_PRIVATE_BUCKET_120_B_LIMIT_ID, limit=120, time_interval=60),
    RateLimit(
        limit_id=SET_LEVERAGE_PATH_URL["non_linear"],
        limit=75,
        time_interval=60,
        linked_limits=[NON_LINEAR_PRIVATE_BUCKET_75_LIMIT_ID],
    ),
    RateLimit(
        limit_id=GET_LAST_FUNDING_RATE_PATH_URL["non_linear"],
        limit=120,
        time_interval=60,
        linked_limits=[NON_LINEAR_PRIVATE_BUCKET_120_B_LIMIT_ID],
    ),
    RateLimit(
        limit_id=GET_POSITIONS_PATH_URL["non_linear"],
        limit=120,
        time_interval=60,
        linked_limits=[NON_LINEAR_PRIVATE_BUCKET_120_A_LIMIT_ID],
    ),
    RateLimit(
        limit_id=PLACE_ACTIVE_ORDER_PATH_URL["non_linear"],
        limit=100,
        time_interval=60,
        linked_limits=[NON_LINEAR_PRIVATE_BUCKET_100_LIMIT_ID],
    ),
    RateLimit(
        limit_id=CANCEL_ACTIVE_ORDER_PATH_URL["non_linear"],
        limit=100,
        time_interval=60,
        linked_limits=[NON_LINEAR_PRIVATE_BUCKET_100_LIMIT_ID],
    ),
    RateLimit(
        limit_id=QUERY_ACTIVE_ORDER_PATH_URL["non_linear"],
        limit=600,
        time_interval=60,
        linked_limits=[NON_LINEAR_PRIVATE_BUCKET_600_LIMIT_ID],
    ),
    RateLimit(
        limit_id=USER_TRADE_RECORDS_PATH_URL["non_linear"],
        limit=120,
        time_interval=60,
    ),
    RateLimit(
        limit_id=GET_WALLET_BALANCE_PATH_URL["non_linear"],
        limit=120,
        time_interval=60,
        linked_limits=[NON_LINEAR_PRIVATE_BUCKET_120_A_LIMIT_ID],
    ),
]

LINEAR_PRIVATE_BUCKET_100_LIMIT_ID = "LinearPrivate100"
LINEAR_PRIVATE_BUCKET_600_LIMIT_ID = "LinearPrivate600"
LINEAR_PRIVATE_BUCKET_75_LIMIT_ID = "LinearPrivate75"
LINEAR_PRIVATE_BUCKET_120_A_LIMIT_ID = "LinearPrivate120A"
_LINEAR_PRIVATE_RATE_LIMITS = [
    RateLimit(limit_id=LINEAR_PRIVATE_BUCKET_100_LIMIT_ID, limit=100, time_interval=60),
    RateLimit(limit_id=LINEAR_PRIVATE_BUCKET_600_LIMIT_ID, limit=600, time_interval=60),
    RateLimit(limit_id=LINEAR_PRIVATE_BUCKET_75_LIMIT_ID, limit=75, time_interval=60),
    RateLimit(limit_id=LINEAR_PRIVATE_BUCKET_120_A_LIMIT_ID, limit=120, time_interval=60),
    RateLimit(
        limit_id=SET_LEVERAGE_PATH_URL["linear"],
        limit=75,
        time_interval=60,
        linked_limits=[LINEAR_PRIVATE_BUCKET_75_LIMIT_ID],
    ),
    RateLimit(
        limit_id=GET_LAST_FUNDING_RATE_PATH_URL["linear"],
        limit=120,
        time_interval=60,
        linked_limits=[LINEAR_PRIVATE_BUCKET_120_A_LIMIT_ID],
    ),
    RateLimit(
        limit_id=GET_POSITIONS_PATH_URL["linear"],
        limit=120,
        time_interval=60,
        linked_limits=[LINEAR_PRIVATE_BUCKET_120_A_LIMIT_ID],
    ),
    RateLimit(
        limit_id=PLACE_ACTIVE_ORDER_PATH_URL["linear"],
        limit=100,
        time_interval=60,
        linked_limits=[LINEAR_PRIVATE_BUCKET_100_LIMIT_ID],
    ),
    RateLimit(
        limit_id=CANCEL_ACTIVE_ORDER_PATH_URL["linear"],
        limit=100,
        time_interval=60,
        linked_limits=[LINEAR_PRIVATE_BUCKET_100_LIMIT_ID],
    ),
    RateLimit(
        limit_id=QUERY_ACTIVE_ORDER_PATH_URL["linear"],
        limit=600,
        time_interval=60,
        linked_limits=[LINEAR_PRIVATE_BUCKET_600_LIMIT_ID],
    ),
    RateLimit(
        limit_id=USER_TRADE_RECORDS_PATH_URL["linear"],
        limit=120,
        time_interval=60,
        linked_limits=[LINEAR_PRIVATE_BUCKET_120_A_LIMIT_ID],
    ),
    RateLimit(
        limit_id=GET_WALLET_BALANCE_PATH_URL["linear"],
        limit=120,
        time_interval=60,
        linked_limits=[NON_LINEAR_PRIVATE_BUCKET_120_A_LIMIT_ID],
    ),
]

RATE_LIMITS = list(chain(_PUBLIC_RATE_LIMITS, _NON_LINEAR_PRIVATE_RATE_LIMITS, _LINEAR_PRIVATE_RATE_LIMITS))
