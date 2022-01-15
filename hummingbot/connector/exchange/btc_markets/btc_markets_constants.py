# A single source of truth for constant variables related to the exchange
# https://api.btcmarkets.net/doc/v3#section/General-notes

from hummingbot.core.api_throttler.data_types import RateLimit

EXCHANGE_NAME = "btc_markets"
REST_URL = "https://api.btcmarkets.net"
WSS_PRIVATE_URL = "wss://socket.btcmarkets.net/v2"
WSS_PUBLIC_URL = "wss://socket.btcmarkets.net/v2"

REST_API_VERSION = "v3"

# REST API Public Endpoints
ACCOUNTS_URL = f"{REST_API_VERSION}/accounts"
MARKETS_URL = f"{REST_API_VERSION}/markets"
ORDERS_URL = f"{REST_API_VERSION}/orders"
BATCH_ORDERS_URL = f"{REST_API_VERSION}/batchorders"
TRADES_URL = f"{REST_API_VERSION}/trades"
TIME_URL = f"{REST_API_VERSION}/time"

WS_METHODS = {
    "TICK": "tick",
    "TRADES": "trade",
    "ORDERS": "orderbook",
    "ORDER_UPDATES": "orderbookUpdate",
    "ORDER_CHANGE": "orderChange",
    "FUND_CHANGE": "fundChange",
    "HEARTBEAT": "heartbeat"
}

"""
Rate Limits - https://api.btcmarkets.net/doc/v3#section/General-Notes
"""

RATE_LIMITS = [
    RateLimit(limit_id=ACCOUNTS_URL, limit=50, time_interval=10),
    RateLimit(limit_id=MARKETS_URL, limit=50, time_interval=10),
    RateLimit(limit_id=ORDERS_URL, limit=30, time_interval=10),
    RateLimit(limit_id=BATCH_ORDERS_URL, limit=50, time_interval=10),
    RateLimit(limit_id=TRADES_URL, limit=50, time_interval=10),
    RateLimit(limit_id=TIME_URL, limit=50, time_interval=10),
]
