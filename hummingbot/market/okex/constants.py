from urllib.parse import urljoin


OKEX_BASE_URL = "https://okex.com/"


OKEX_SYMBOLS_URL = urljoin(OKEX_BASE_URL, "spot/v3/instruments/ticker")
OKEX_DEPTH_URL = urljoin(OKEX_BASE_URL, "spot/v3/instruments/{trading_pair}/book")

# Auth required
# Doesn't include base URL as the tail is required to generate the signature

OKEX_PLACE_ORDER = "api/spot/v3/orders"
OKEX_BALANCE_URL = "api/spot/v3/accounts"
OKEX_INSTRUMENTS_URL = "api/spot/v3/instruments"


# WS
OKCOIN_WS_URI = "wss://real.okex.com:8443/ws/v3"