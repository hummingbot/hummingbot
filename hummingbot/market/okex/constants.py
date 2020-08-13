from urllib.parse import urljoin


OKEX_BASE_URL = "https://okex.com/api/"


OKEX_SYMBOLS_URL = urljoin(OKEX_BASE_URL, "spot/v3/instruments/ticker")
OKEX_DEPTH_URL = urljoin(OKEX_BASE_URL, "spot/v3/instruments/{trading_pair}/book")

# Auth required
# Doesn't include base URL as the tail is required to generate the signature

OKEX_PLACE_ORDER = "spot/v3/orders"


# WS
OKCOIN_WS_URI = "wss://real.okex.com:8443/ws/v3"