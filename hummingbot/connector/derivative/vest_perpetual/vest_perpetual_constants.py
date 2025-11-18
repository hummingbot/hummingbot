"""
Vest Perpetual API constants.
"""

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

EXCHANGE_NAME = "vest_perpetual"
DEFAULT_DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = f"{EXCHANGE_NAME}_testnet"

# Base URLs
REST_URL_PROD = "https://server-prod.hz.vestmarkets.com/v2"
REST_URL_DEV = "https://server-dev.hz.vestmarkets.com/v2"
WSS_URL_PROD = "wss://ws-prod.hz.vestmarkets.com/ws-api"
WSS_URL_DEV = "wss://ws-dev.hz.vestmarkets.com/ws-api"

REST_URLS = {
    DEFAULT_DOMAIN: REST_URL_PROD,
    TESTNET_DOMAIN: REST_URL_DEV,
    "mainnet": REST_URL_PROD,
    "testnet": REST_URL_DEV,
}

WSS_URLS = {
    DEFAULT_DOMAIN: WSS_URL_PROD,
    TESTNET_DOMAIN: WSS_URL_DEV,
    "mainnet": WSS_URL_PROD,
    "testnet": WSS_URL_DEV,
}

# Default to production
REST_URL = REST_URL_PROD
WSS_URL = WSS_URL_PROD

# Contract addresses
VERIFYING_CONTRACT_PROD = "0x919386306C47b2Fe1036e3B4F7C40D22D2461a23"
VERIFYING_CONTRACT_DEV = "0x8E4D87AEf4AC4D5415C35A12319013e34223825B"
VERIFYING_CONTRACT = VERIFYING_CONTRACT_PROD

# REST endpoints
REGISTER_PATH_URL = "/register"
EXCHANGE_INFO_PATH_URL = "/exchangeInfo"
TICKER_LATEST_PATH_URL = "/ticker/latest"
TICKER_24HR_PATH_URL = "/ticker/24hr"
FUNDING_HISTORY_PATH_URL = "/funding/history"
KLINES_PATH_URL = "/klines"
TRADES_PATH_URL = "/trades"
DEPTH_PATH_URL = "/depth"
ACCOUNT_PATH_URL = "/account"
ACCOUNT_NONCE_PATH_URL = "/account/nonce"
ACCOUNT_LEVERAGE_PATH_URL = "/account/leverage"
ORDERS_PATH_URL = "/orders"
ORDERS_CANCEL_PATH_URL = "/orders/cancel"
LP_PATH_URL = "/lp"
TRANSFER_WITHDRAW_PATH_URL = "/transfer/withdraw"
TRANSFER_PATH_URL = "/transfer"
LISTEN_KEY_PATH_URL = "/account/listenKey"

# WebSocket channels
WS_TICKERS_CHANNEL = "tickers"
WS_KLINE_CHANNEL = "{symbol}@kline_{interval}"
WS_DEPTH_CHANNEL = "{symbol}@depth"
WS_TRADES_CHANNEL = "{symbol}@trades"
WS_ACCOUNT_PRIVATE_CHANNEL = "account_private"

# WebSocket events
WS_EVENT_ORDER = "ORDER"
WS_EVENT_LP = "LP"
WS_EVENT_TRANSFER = "TRANSFER"

# Order types
ORDER_TYPE_MARKET = "MARKET"
ORDER_TYPE_LIMIT = "LIMIT"
ORDER_TYPE_STOP_LOSS = "STOP_LOSS"
ORDER_TYPE_TAKE_PROFIT = "TAKE_PROFIT"
ORDER_TYPE_LIQUIDATION = "LIQUIDATION"

# Order status
ORDER_STATUS_NEW = "NEW"
ORDER_STATUS_PARTIALLY_FILLED = "PARTIALLY_FILLED"
ORDER_STATUS_FILLED = "FILLED"
ORDER_STATUS_CANCELLED = "CANCELLED"
ORDER_STATUS_REJECTED = "REJECTED"

# Time in force
TIME_IN_FORCE_GTC = "GTC"
TIME_IN_FORCE_FOK = "FOK"

# Symbol status
SYMBOL_STATUS_TRADING = "TRADING"
SYMBOL_STATUS_HALT = "HALT"

# Heartbeat interval for WebSocket ping/pong (seconds)
HEARTBEAT_TIME_INTERVAL = 30

# Rate limits
# According to docs, rate limits are enforced but specific values not documented
# Using conservative defaults
RATE_LIMITS = [
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=TICKER_LATEST_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=TICKER_24HR_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=FUNDING_HISTORY_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=KLINES_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=TRADES_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=DEPTH_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=ACCOUNT_PATH_URL, limit=5, time_interval=1),
    RateLimit(limit_id=ACCOUNT_NONCE_PATH_URL, limit=5, time_interval=1),
    RateLimit(limit_id=ACCOUNT_LEVERAGE_PATH_URL, limit=5, time_interval=1),
    RateLimit(limit_id=ORDERS_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=ORDERS_CANCEL_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=LP_PATH_URL, limit=5, time_interval=1),
    RateLimit(limit_id=TRANSFER_WITHDRAW_PATH_URL, limit=2, time_interval=1),
    RateLimit(limit_id=TRANSFER_PATH_URL, limit=5, time_interval=1),
    RateLimit(limit_id=LISTEN_KEY_PATH_URL, limit=5, time_interval=1),
    RateLimit(limit_id=REGISTER_PATH_URL, limit=1, time_interval=10),
]
