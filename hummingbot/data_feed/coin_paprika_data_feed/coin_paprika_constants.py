from hummingbot.core.api_throttler.data_types import RateLimit

BASE_REST_URL = "https://api.coinpaprika.com/v1"

ALL_TICKERS_ENDPOINT = "/tickers"
TICKER_ENDPOINT = "/tickers/{}"
HEALTH_CHECK_ENDPOINT = TICKER_ENDPOINT.format("btc-bitcoin")  # get a single ticker

UNIVERSAL_QUOTE_TOKEN = "USD"

# Quote currencies accepted by the `quotes` parameter of the /tickers endpoint, as listed in the
# endpoint documentation (https://api.coinpaprika.com, "Get tickers for all active coins").
SUPPORTED_QUOTE_TOKENS = frozenset(
    (
        "BTC", "ETH", "USD", "EUR", "PLN", "KRW", "GBP", "CAD", "JPY", "RUB", "TRY", "NZD", "AUD", "CHF",
        "UAH", "HKD", "SGD", "NGN", "PHP", "MXN", "BRL", "THB", "CLP", "CNY", "CZK", "DKK", "HUF", "IDR",
        "ILS", "INR", "MYR", "NOK", "PKR", "SEK", "TWD", "ZAR", "VND", "BOB", "COP", "PEN", "ARS", "ISK",
    )
)

# The keyless API allows 10 requests per second per IP and 20,000 requests per month. Caching the
# /tickers response for 3 minutes keeps a bot that runs around the clock at roughly 14,400 requests
# per month, within the keyless quota.
TICKERS_CACHE_TTL = 3 * 60.0

REQUESTS_LIMIT_ID = "requestsLimitID"
REQUESTS_LIMIT = 10
SECOND = 1

RATE_LIMITS = [
    RateLimit(limit_id=REQUESTS_LIMIT_ID, limit=REQUESTS_LIMIT, time_interval=SECOND),
]
