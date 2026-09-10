from typing import List

from hummingbot.core.api_throttler.data_types import RateLimit

EXCHANGE_NAME = "kalshi_perpetual"

# Production only. Kalshi also has a demo environment (https://external-api.demo.kalshi.co/trade-api/v2), which is
# not supported. The domain selects the base URL in web_utils.
DEFAULT_DOMAIN = EXCHANGE_NAME

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
MARKET_PATH_URL = "/margin/markets/{ticker}"
ORDER_BOOK_PATH_URL = "/margin/markets/{ticker}/orderbook"
FUNDING_RATE_ESTIMATE_PATH_URL = "/margin/funding_rates/estimate"

# No SERVER_TIME_PATH_URL: Kalshi has no server-time endpoint and documents no tolerance window for the
# KALSHI-ACCESS-TIMESTAMP (ms) signed header, so requests are signed with local time and never resynced.
# https://docs.kalshi.com/getting_started/api_keys

# Filled in with the main class, once every REST call is known. Until then the throttler lets requests through.
RATE_LIMITS: List[RateLimit] = []

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
