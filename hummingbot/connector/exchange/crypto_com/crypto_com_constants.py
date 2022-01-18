# A single source of truth for constant variables related to the exchange

from hummingbot.core.api_throttler.data_types import RateLimit

EXCHANGE_NAME = "crypto_com"
REST_URL = "https://api.crypto.com/"

API_VERSION = "v2"

# WSS_PRIVATE_URL = "wss://stream.crypto.com/v2/user"
WSS_PRIVATE_URL = "wss://d289dek49b4wqs.cloudfront.net/v2/user"
# WSS_PUBLIC_URL = "wss://stream.crypto.com/v2/market"
WSS_PUBLIC_URL = "wss://d10tq1f9ygdz7y.cloudfront.net/v2/market"

# REST API ENDPOINTS
GET_ORDER_BOOK_PATH_URL = "/public/get-book"
GET_TICKER_PATH_URL = "/public/get-ticker"
GET_TRADING_RULES_PATH_URL = "/public/get-instruments"
CREATE_ORDER_PATH_URL = "/private/create-order"
CANCEL_ORDER_PATH_URL = "/private/cancel-order"
GET_ACCOUNT_SUMMARY_PATH_URL = "/private/get-account-summary"
GET_ORDER_DETAIL_PATH_URL = "/private/get-order-detail"
GET_OPEN_ORDERS_PATH_URL = "/private/get-open-orders"

# Crypto.com has a per method API limit

RATE_LIMITS = [
    RateLimit(limit_id=GET_TRADING_RULES_PATH_URL, limit=100, time_interval=1),
    RateLimit(limit_id=CREATE_ORDER_PATH_URL, limit=15, time_interval=0.1),
    RateLimit(limit_id=CANCEL_ORDER_PATH_URL, limit=15, time_interval=0.1),
    RateLimit(limit_id=GET_ACCOUNT_SUMMARY_PATH_URL, limit=3, time_interval=0.1),
    RateLimit(limit_id=GET_ORDER_DETAIL_PATH_URL, limit=30, time_interval=0.1),
    RateLimit(limit_id=GET_OPEN_ORDERS_PATH_URL, limit=3, time_interval=0.1),
    RateLimit(limit_id=GET_ORDER_BOOK_PATH_URL, limit=100, time_interval=1),
    RateLimit(limit_id=GET_TICKER_PATH_URL, limit=100, time_interval=1),
]


API_REASONS = {
    0: "Success",
    10001: "Malformed request, (E.g. not using application/json for REST)",
    10002: "Not authenticated, or key/signature incorrect",
    10003: "IP address not whitelisted",
    10004: "Missing required fields",
    10005: "Disallowed based on user tier",
    10006: "Requests have exceeded rate limits",
    10007: "Nonce value differs by more than 30 seconds from server",
    10008: "Invalid method specified",
    10009: "Invalid date range",
    20001: "Duplicated record",
    20002: "Insufficient balance",
    30003: "Invalid instrument_name specified",
    30004: "Invalid side specified",
    30005: "Invalid type specified",
    30006: "Price is lower than the minimum",
    30007: "Price is higher than the maximum",
    30008: "Quantity is lower than the minimum",
    30009: "Quantity is higher than the maximum",
    30010: "Required argument is blank or missing",
    30013: "Too many decimal places for Price",
    30014: "Too many decimal places for Quantity",
    30016: "The notional amount is less than the minimum",
    30017: "The notional amount exceeds the maximum",
}
