from hummingbot.core.api_throttler.data_types import RateLimit

DEFAULT_DOMAIN = "com"

HBOT_ORDER_ID_PREFIX = "bit2c-"
MAX_ORDER_ID_LEN = 32

# Base URL
REST_URL = "https://bit2c.co.il/"
WSS_URL = ""

# Public API endpoints or Bit2cClient function
TICKER_PRICE_CHANGE_PATH_URL = "Exchanges/{}/Ticker.json"
TICKER_BOOK_PATH_URL = "Exchanges/{}/Ticker.json"
EXCHANGE_INFO_PATH_URL = ""
PING_PATH_URL = "Exchanges/BtcNis/orderbook-top.json"
SNAPSHOT_PATH_URL = "Exchanges/{}/orderbook.json"

# Private API endpoints or Bit2cClient function
ACCOUNTS_PATH_URL = "Account/Balance"
CREATE_LIMIT_ORDER_PATH_URL = "Order/AddOrder"
CREATE_MARKET_BUY_ORDER_PATH_URL = "Order/AddOrderMarketPriceBuy"
CREATE_MARKET_SELL_ORDER_PATH_URL = "Order/AddOrderMarketPriceSell"
CANCEL_ORDER_PATH_URL = "Order/CancelOrder"
GET_ORDER_PATH_URL = "Order/GetById"
GET_TRADES_PATH_URL = "Order/HistoryByOrderId"

# Bit2c params

SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

TIME_IN_FORCE_GTC = "GTC"  # Good till cancelled
TIME_IN_FORCE_IOC = "IOC"  # Immediate or cancel
TIME_IN_FORCE_FOK = "FOK"  # Fill or kill


# ExchangeInfo endpoint - Trading Rules for the four trading pairs on Bit2c
EXCHANGE_INFO = {
    "symbols": [
        {
            "symbol": "BtcNis",
            "baseAsset": "BTC",
            "quoteAsset": "NIS",
            "baseAssetPrecision": 8,
            "quoteAssetPrecision": 2,
            "minNotional": 13.0,
        },
        {
            "symbol": "EthNis",
            "baseAsset": "ETH",
            "quoteAsset": "NIS",
            "baseAssetPrecision": 8,
            "quoteAssetPrecision": 2,
            "minNotional": 13.0,
        },
        {
            "symbol": "LtcNis",
            "baseAsset": "LTC",
            "quoteAsset": "NIS",
            "baseAssetPrecision": 8,
            "quoteAssetPrecision": 2,
            "minNotional": 13.0,
        },
        {
            "symbol": "UsdcNis",
            "baseAsset": "USDC",
            "quoteAsset": "NIS",
            "baseAssetPrecision": 8,
            "quoteAssetPrecision": 2,
            "minNotional": 13.0,
        }
    ]
}


RATE_LIMITS = [
    RateLimit(limit_id=TICKER_PRICE_CHANGE_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=TICKER_BOOK_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=PING_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=10, time_interval=1),
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=1, time_interval=1),
    RateLimit(limit_id=CREATE_LIMIT_ORDER_PATH_URL, limit=1, time_interval=1),
    RateLimit(limit_id=CREATE_MARKET_BUY_ORDER_PATH_URL, limit=1, time_interval=1),
    RateLimit(limit_id=CREATE_MARKET_SELL_ORDER_PATH_URL, limit=1, time_interval=1),
    RateLimit(limit_id=CANCEL_ORDER_PATH_URL, limit=20, time_interval=1),
    RateLimit(limit_id=GET_ORDER_PATH_URL, limit=20, time_interval=1),
    RateLimit(limit_id=GET_TRADES_PATH_URL, limit=20, time_interval=1),
]

ORDER_NOT_EXIST_MESSAGE = "No order found"
UNKNOWN_ORDER_MESSAGE = "Order with id"
