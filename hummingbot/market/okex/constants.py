from urllib.parse import urljoin


OKEX_BASE_URL = "https://okex.com/api/"

OKEX_SYMBOLS_URL = urljoin(OKEX_BASE_URL, "spot/v3/instruments/ticker")
OKEX_DEPTH_URL = urljoin(OKEX_BASE_URL, "spot/v3/instruments/{trading_pair}/book")

OKCOIN_WS_URI = "wss://real.okex.com:8443/ws/v3"


HUOBI_API_ENDPOINT = "https://api.huobi.pro"
HUOBI_WS_ENDPOINT = "wss://api.huobi.pro/ws/v2"