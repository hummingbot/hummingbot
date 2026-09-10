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

# No SERVER_TIME_PATH_URL: Kalshi has no server-time endpoint and documents no tolerance window for the
# KALSHI-ACCESS-TIMESTAMP (ms) signed header, so requests are signed with local time and never resynced.
# https://docs.kalshi.com/getting_started/api_keys
