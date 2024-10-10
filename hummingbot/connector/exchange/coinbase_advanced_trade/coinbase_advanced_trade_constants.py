from enum import Enum
from typing import Tuple

from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "Coinbase Advanced Trade"

CHANGELOG_URL = "https://docs.cdp.coinbase.com/advanced-trade/docs/changelog"
LATEST_UPDATE = "2024-SEP-04"
# curl https://docs.cdp.coinbase.com/advanced-trade/docs/changelog | md5sum
CHANGELOG_HASH = "4825e9a0e67b58f6be38f7e411637b87"

COINBASE_ADVANCED_TRADE_CLASS_PREFIX = "CoinbaseAdvancedTrade"

DEFAULT_DOMAIN = "com"

HBOT_ORDER_ID_PREFIX = "CBAT-"
MAX_ORDER_ID_LEN = 32
HBOT_BROKER_ID = "Hummingbot"

# Base URL
SIGNIN_URL = "https://api.coinbase.{domain}/v2"
REST_URL = "https://api.coinbase.{domain}/api/v3"
WSS_URL = "wss://advanced-trade-ws.coinbase.{domain}"
USER_WSS_URL = "wss://advanced-trade-ws-user.coinbase.{domain}"

# Coinbase Signin API endpoints
EXCHANGE_RATES_USD_EP = "/exchange-rates"
EXCHANGE_RATES_QUOTE_EP = "/exchange-rates?currency={quote_token}"
EXCHANGE_RATES_QUOTE_LIMIT_ID = "ExchangeRatesQuote"
CURRENCIES_EP = "/currencies"
CRYPTO_CURRENCIES_EP = "/currencies/crypto"

SIGNIN_ENDPOINTS = {
    EXCHANGE_RATES_USD_EP,
    EXCHANGE_RATES_QUOTE_LIMIT_ID,
    CURRENCIES_EP,
    CRYPTO_CURRENCIES_EP,
}

# Private API endpoints
SERVER_TIME_EP = "/brokerage/time"
ALL_PAIRS_EP = "/brokerage/products"
PAIR_TICKER_EP = "/brokerage/products/{product_id}"
PAIR_TICKER_RATE_LIMIT_ID = "PairTicker"
PAIR_TICKER_24HR_EP = "/brokerage/products/{product_id}/ticker"
PAIR_TICKER_24HR_RATE_LIMIT_ID = "PairTicker24Hr"
ORDER_EP = "/brokerage/orders"
BATCH_CANCEL_EP = "/brokerage/orders/batch_cancel"
GET_ORDER_STATUS_EP = "/brokerage/orders/historical/{order_id}"
GET_ORDER_STATUS_RATE_LIMIT_ID = "GetOrderStatus"
GET_STATUS_BATCH_EP = "/brokerage/orders/historical/batch"
FILLS_EP = "/brokerage/orders/historical/fills"
TRANSACTIONS_SUMMARY_EP = "/brokerage/transaction_summary"
ACCOUNTS_LIST_EP = "/brokerage/accounts"
ACCOUNT_EP = "/brokerage/accounts/{account_uuid}"
ACCOUNT_RATE_LIMIT_ID = "Account"
SNAPSHOT_EP = "/brokerage/product_book"

PRIVATE_REST_ENDPOINTS = {
    ALL_PAIRS_EP,
    PAIR_TICKER_RATE_LIMIT_ID,
    PAIR_TICKER_24HR_RATE_LIMIT_ID,
    ORDER_EP,
    BATCH_CANCEL_EP,
    GET_ORDER_STATUS_RATE_LIMIT_ID,
    GET_STATUS_BATCH_EP,
    FILLS_EP,
    TRANSACTIONS_SUMMARY_EP,
    ACCOUNTS_LIST_EP,
    ACCOUNT_RATE_LIMIT_ID,
    SNAPSHOT_EP,
}

PUBLIC_REST_ENDPOINTS = {
    SERVER_TIME_EP,
}

WS_HEARTBEAT_TIME_INTERVAL = 30


class WebsocketAction(Enum):
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"


# https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels
# TODO: this is not exclusively ORDER SUBSCRIPTION, please review the naming
WS_ORDER_SUBSCRIPTION_KEYS: Tuple[str, ...] = ("level2", "market_trades")
WS_ORDER_SUBSCRIPTION_CHANNELS: bidict[str, str] = bidict({"l2_data": "order_book_diff", "market_trades": "trade"})
WS_MAX_MSG_SIZE = 8 * 1024 * 1024

WS_USER_SUBSCRIPTION_KEYS: str = "user"
# WS_USER_SUBSCRIPTION_KEYS: Tuple[str, ...] = ("user",)
WS_USER_SUBSCRIPTION_CHANNELS: bidict[str, str] = bidict({k: k for k in WS_USER_SUBSCRIPTION_KEYS})

WS_OTHERS_SUBSCRIPTION_KEYS: Tuple[str, ...] = ("ticker", "ticker_batch", "status", "candles")
WS_OTHERS_SUBSCRIPTION_CHANNELS: bidict[str, str] = bidict({k: k for k in WS_OTHERS_SUBSCRIPTION_KEYS})

# CoinbaseAdvancedTrade params
SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

# Rate Limit Type
PRIVATE_REST_REQUESTS = "PRIVATE_REST_REQUESTS"
MAX_PRIVATE_REST_REQUESTS_S = 30

PUBLIC_REST_REQUESTS = "PUBLIC_REST_REQUESTS"
MAX_PUBLIC_REST_REQUESTS_S = 10

SIGNIN_REQUESTS = "SIGNIN_REQUESTS"
MAX_SIGNIN_REQUESTS_H = 10000

WSS_REQUESTS = "WSS_REQUESTS"
MAX_WSS_REQUESTS_S = 750

# Rate Limit time intervals
ONE_SECOND = 1
ONE_MINUTE = 60
ONE_HOUR = 3600
ONE_DAY = 86400

# Order States
ORDER_STATE = {
    "OPEN": OrderState.OPEN,
    "PENDING": OrderState.PENDING_CREATE,
    "FILLED": OrderState.FILLED,
    "CANCELLED": OrderState.CANCELED,
    "EXPIRED": OrderState.FAILED,
    "FAILED": OrderState.FAILED,
    # Not directly from exchange
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
}
# Oddly, order can be in unknown state ???
ORDER_STATUS_NOT_FOUND_ERROR_CODE = "UNKNOWN_ORDER_STATUS"

PRIVATE_REST_RATE_LIMITS = [
    RateLimit(limit_id=endpoint,
              limit=MAX_PRIVATE_REST_REQUESTS_S,
              time_interval=ONE_SECOND,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_REST_REQUESTS, 1)]) for endpoint in PRIVATE_REST_ENDPOINTS]

PUBLIC_REST_RATE_LIMITS = [
    RateLimit(limit_id=endpoint,
              limit=MAX_PUBLIC_REST_REQUESTS_S,
              time_interval=ONE_SECOND,
              linked_limits=[LinkedLimitWeightPair(PRIVATE_REST_REQUESTS, 1)]) for endpoint in PUBLIC_REST_ENDPOINTS]

SIGNIN_RATE_LIMITS = [
    RateLimit(limit_id=endpoint,
              limit=MAX_SIGNIN_REQUESTS_H,
              time_interval=ONE_HOUR,
              linked_limits=[LinkedLimitWeightPair(SIGNIN_REQUESTS, 1)]) for endpoint in SIGNIN_ENDPOINTS]

RATE_LIMITS = [
    RateLimit(limit_id=PRIVATE_REST_REQUESTS, limit=MAX_PRIVATE_REST_REQUESTS_S, time_interval=ONE_SECOND),
    RateLimit(limit_id=PUBLIC_REST_REQUESTS, limit=MAX_PUBLIC_REST_REQUESTS_S, time_interval=ONE_SECOND),
    RateLimit(limit_id=SIGNIN_REQUESTS, limit=MAX_SIGNIN_REQUESTS_H, time_interval=ONE_HOUR),
    RateLimit(limit_id=WSS_REQUESTS, limit=MAX_WSS_REQUESTS_S, time_interval=ONE_SECOND),
]

RATE_LIMITS.extend(PRIVATE_REST_RATE_LIMITS)
RATE_LIMITS.extend(PUBLIC_REST_RATE_LIMITS)
RATE_LIMITS.extend(SIGNIN_RATE_LIMITS)
