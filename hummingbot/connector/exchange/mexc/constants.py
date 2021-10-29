from urllib.parse import urljoin

# URLs

MEXC_BASE_URL = "https://www.mexc.com"


MEXC_SYMBOL_URL = '/open/api/v2/market/symbols'
MEXC_TICKERS_URL = '/open/api/v2/market/ticker'
MEXC_DEPTH_URL = '/open/api/v2/market/depth?symbol={trading_pair}&depth=200'
MEXC_PRICE_URL = '/open/api/v2/market/ticker?symbol={trading_pair}'
MEXC_PING_URL = '/open/api/v2/common/ping'


MEXC_PLACE_ORDER = "/open/api/v2/order/place"
MEXC_ORDER_DETAILS_URL = '/open/api/v2/order/query'
MEXC_ORDER_CANCEL = '/open/api/v2/order/cancel'
MEXC_BATCH_ORDER_CANCEL = '/open/api/v2/order/cancel'
MEXC_BALANCE_URL = '/open/api/v2/account/info'

# WS
MEXC_WS_URI_PUBLIC = 'wss://wbs.mexc.com/raw/ws'


