from decimal import Decimal
from typing import List

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

EXCHANGE_NAME = "kalshi_perpetual"

# Production only. Kalshi also has a demo environment (https://external-api.demo.kalshi.co/trade-api/v2), which is
# not supported. The domain selects the base URL in web_utils.
DEFAULT_DOMAIN = EXCHANGE_NAME

# Margin markets are tickers like KXBTCPERP (BTC-USD), quoted, margined and settled in USD.
MARKET_TICKER_PREFIX = "KX"
MARKET_TICKER_SUFFIX = "PERP"
COLLATERAL_TOKEN = "USD"

# Kalshi requires a client_order_id but documents no length or charset limit; it recommends UUIDs (36 characters),
# so generated ids stay within that length. https://docs.kalshi.com/margin-rest/orders/create-order
CLIENT_ORDER_ID_PREFIX = "HBOT"
MAX_ORDER_ID_LEN = 36

# Base URLs include the API version prefix; path constants start with "/" and match the docs verbatim
# (e.g. "/margin/exchange/status"). Requests are signed over the full path, "/trade-api/v2" included.
# https://docs.kalshi.com/margin
REST_URLS = {
    DEFAULT_DOMAIN: "https://external-api.kalshi.com/trade-api/v2",
}

# Every channel, public ones included, needs the signed handshake (unauthenticated connections get HTTP 401).
# https://docs.kalshi.com/margin-ws/websockets/websocket-connection
WSS_URLS = {
    DEFAULT_DOMAIN: "wss://external-api-margin-ws.kalshi.com/trade-api/ws/v2/margin",
}
# Kalshi sends a ping frame every 10 seconds and WSConnection answers it with a pong.
# https://docs.kalshi.com/margin-ws/websockets/connection-keep-alive
HEARTBEAT_TIME_INTERVAL = 10

# Public REST endpoints
EXCHANGE_STATUS_PATH_URL = "/margin/exchange/status"
MARKETS_PATH_URL = "/margin/markets"
MARKET_PATH_URL = "/margin/markets/{ticker}"
ORDER_BOOK_PATH_URL = "/margin/markets/{ticker}/orderbook"
FUNDING_RATE_ESTIMATE_PATH_URL = "/margin/funding_rates/estimate"

# Private REST endpoints. Orders are cancelled and queried by Kalshi's order_id only (no client_order_id lookup).
ORDERS_PATH_URL = "/margin/orders"
ORDER_PATH_URL = "/margin/orders/{order_id}"
FILLS_PATH_URL = "/margin/fills"
POSITIONS_PATH_URL = "/margin/positions"
BALANCE_PATH_URL = "/margin/balance"
FUNDING_HISTORY_PATH_URL = "/margin/funding_history"
FEE_TIERS_PATH_URL = "/margin/fee_tiers"

# Throttler ids for paths used with more than one HTTP method
CREATE_ORDER_LIMIT_ID = f"POST{ORDERS_PATH_URL}"
GET_ORDER_LIMIT_ID = f"GET{ORDER_PATH_URL}"
CANCEL_ORDER_LIMIT_ID = f"DELETE{ORDER_PATH_URL}"

# Order parameters. Kalshi only takes limit orders (price is required), so market orders are sent as
# immediate-or-cancel limit orders priced this far through the book. reduce_only is rejected on resting orders, so the
# connector emulates it for them.
TIME_IN_FORCE_GTC = "good_till_canceled"
TIME_IN_FORCE_IOC = "immediate_or_cancel"
SELF_TRADE_PREVENTION_TYPE = "taker_at_cross"
MARKET_ORDER_SLIPPAGE = Decimal("0.05")

# Funding is settled every 8 hours (04:00, 12:00 and 20:00 UTC); payments are polled more often than that.
FUNDING_FEE_POLL_INTERVAL = 600

# No SERVER_TIME_PATH_URL: Kalshi has no server-time endpoint and documents no tolerance window for the
# KALSHI-ACCESS-TIMESTAMP (ms) signed header, so requests are signed with local time and never resynced.
# https://docs.kalshi.com/getting_started/api_keys

# Perps traffic draws from its own token buckets (separate from event contracts): a Read bucket for GETs and a Write
# bucket for order placement and cancels. Budgets are the Basic tier's; every margin call costs 10 tokens except
# GET /margin/balance: 5, or 50 with compute_available_balance=true (it scans all resting orders), which the connector
# always passes. https://docs.kalshi.com/getting_started/rate_limits
READ_BUCKET_LIMIT_ID = "PerpsReadBucket"
WRITE_BUCKET_LIMIT_ID = "PerpsWriteBucket"
READ_TOKENS_PER_SECOND = 200
WRITE_TOKENS_PER_SECOND = 100
DEFAULT_REQUEST_COST = 10
BALANCE_REQUEST_COST = 50


def _endpoint_limit(limit_id: str, bucket_id: str, bucket_tokens: int, cost: int = DEFAULT_REQUEST_COST) -> RateLimit:
    return RateLimit(
        limit_id=limit_id,
        limit=bucket_tokens // cost,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(bucket_id, cost)],
    )


RATE_LIMITS: List[RateLimit] = [
    RateLimit(limit_id=READ_BUCKET_LIMIT_ID, limit=READ_TOKENS_PER_SECOND, time_interval=1),
    RateLimit(limit_id=WRITE_BUCKET_LIMIT_ID, limit=WRITE_TOKENS_PER_SECOND, time_interval=1),
    *[
        _endpoint_limit(limit_id, READ_BUCKET_LIMIT_ID, READ_TOKENS_PER_SECOND)
        for limit_id in (
            EXCHANGE_STATUS_PATH_URL, MARKETS_PATH_URL, MARKET_PATH_URL, ORDER_BOOK_PATH_URL,
            FUNDING_RATE_ESTIMATE_PATH_URL, GET_ORDER_LIMIT_ID, FILLS_PATH_URL, POSITIONS_PATH_URL,
            FUNDING_HISTORY_PATH_URL, FEE_TIERS_PATH_URL,
        )
    ],
    _endpoint_limit(BALANCE_PATH_URL, READ_BUCKET_LIMIT_ID, READ_TOKENS_PER_SECOND, cost=BALANCE_REQUEST_COST),
    _endpoint_limit(CREATE_ORDER_LIMIT_ID, WRITE_BUCKET_LIMIT_ID, WRITE_TOKENS_PER_SECOND),
    _endpoint_limit(CANCEL_ORDER_LIMIT_ID, WRITE_BUCKET_LIMIT_ID, WRITE_TOKENS_PER_SECOND),
]

# Public WebSocket channels to subscribe to, and the message types they produce
WS_ORDER_BOOK_CHANNEL = "orderbook_delta"
WS_TRADE_CHANNEL = "trade"
WS_TICKER_CHANNEL = "ticker"
WS_ORDER_BOOK_SNAPSHOT_MESSAGE = "orderbook_snapshot"
WS_ORDER_BOOK_DELTA_MESSAGE = "orderbook_delta"
WS_TRADE_MESSAGE = "trade"
WS_TICKER_MESSAGE = "ticker"
WS_SUBSCRIBED_MESSAGE = "subscribed"
WS_ERROR_MESSAGE = "error"

# Private WebSocket channels. There is no balance or position channel: those are polled over REST.
# https://docs.kalshi.com/margin-ws/websockets/user-fills
# https://docs.kalshi.com/margin-ws/websockets/user-orders
WS_FILL_CHANNEL = "fill"
WS_USER_ORDERS_CHANNEL = "user_orders"
WS_FILL_MESSAGE = "fill"
WS_USER_ORDER_MESSAGE = "user_order"
