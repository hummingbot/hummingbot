from hummingbot.core.api_throttler.data_types import RateLimit

EXCHANGE_NAME = "wazirx"
WSS_URL = "wss://stream.wazirx.com/stream"

# REST API ENDPOINTS
WAZIRX_API_BASE = "https://api.wazirx.com/sapi/v1"
CHECK_NETWORK_PATH_URL = "ping"
GET_TRADING_RULES_PATH_URL = "exchangeInfo"
ORDER_PATH_URL = "order"
MY_TRADES_PATH_URL = "myTrades"
FUND_DETAILS_PATH_URL = "funds"
GET_RECENT_TRADES = "trades"
CREATE_WSS_AUTH_TOKEN = "create_auth_token"
GET_EXCHANGE_INFO = "exchangeInfo"
GET_ORDERBOOK = "depth"
GET_TICKER_24H = "tickers/24hr"

RATE_LIMITS = [
    RateLimit(limit_id=CHECK_NETWORK_PATH_URL, limit=6000, time_interval=300),
    RateLimit(limit_id=GET_TRADING_RULES_PATH_URL, limit=6000, time_interval=300),
    RateLimit(limit_id=ORDER_PATH_URL, limit=6000, time_interval=300),
    RateLimit(limit_id=MY_TRADES_PATH_URL, limit=6000, time_interval=300),
    RateLimit(limit_id=FUND_DETAILS_PATH_URL, limit=6000, time_interval=300),
    RateLimit(limit_id=GET_RECENT_TRADES, limit=6000, time_interval=300),
    RateLimit(limit_id=GET_TICKER_24H, limit=6000, time_interval=300),
    RateLimit(limit_id=CREATE_WSS_AUTH_TOKEN, limit=6000, time_interval=300),
    RateLimit(limit_id=GET_EXCHANGE_INFO, limit=6000, time_interval=300),
    RateLimit(limit_id=GET_ORDERBOOK, limit=6000, time_interval=300),
]

API_FAIL_REASONS = {
    2001: "Authorization failed",
    2002: "CreateOrderError",
    2003: "CancelOrderError",
    2004: "OrderNotFoundError",
    2005: "IncorrectSignatureError",
    2016: "UserNotVerifiedError",
    2021: "UnauthorizedAccess",
    2026: "AccountBalanceInsufficient",
    2031: "MinimumOrderPlacementVolumeError",
    2032: "InvalidMarketError",
    2033: "InvalidCurrencyError",
    2043: "InternalServerError",
    2046: "NoVerifiedBankDetailsPresent",
    2052: "UserBlocked",
    2063: "OrderPaused",
    2064: "MarketDelisted",
    2065: "UserNotFound",
    2067: "ActionBlocked",
    2068: "GenericError",
    2069: "CryptoRateNotFound",
    2070: "MaxOrderPriceError",
    2074: "LowBalanceError",
    2075: "CurrencyNotAllowedError",
    2077: "MinOrderPriceError",
    2078: "AccessDeniedError",
    2079: "InvalidAmountError",
    2080: "UnsupportedOrderTypeError",
    2086: "InvalidPriceError",
    2097: "TimestampUsedError",
    2098: "RequestOutOfRecvWindowError",
    2112: "MissingUapiKey",
    2113: "InvalidRecvWindowError",
    2114: "InvalidOrderTypeError",
    2115: "SignatureNotFoundError",
    2128: "IpNotWhitelistedError",
    94001: "BadRequest",
}
