from urllib.parse import urljoin


# URLs

OKEX_BASE_URL = "https://www.okex.com/"

OKEX_INSTRUMENTS_URL = urljoin(OKEX_BASE_URL, 'api/v5/public/instruments?instType=SPOT')
OKEX_TICKERS_URL = urljoin(OKEX_BASE_URL, 'api/v5/market/tickers?instType=SPOT')
OKEX_DEPTH_URL = urljoin(OKEX_BASE_URL, 'api/v5/market/books?instId={trading_pair}&sz=200')     # Size=200 by default?
OKEX_PRICE_URL = urljoin(OKEX_BASE_URL, 'api/v5/public/instruments/{trading_pair}/ticker')

# Doesn't include base URL as the tail is required to generate the signature

OKEX_SERVER_TIME = 'api/v5/public/time'

# Auth required

OKEX_PLACE_ORDER = "api/v5/trade/order"
OKEX_ORDER_DETAILS_URL = 'api/v5/trade/order?ordId={ordId}&instId={trading_pair}'
OKEX_ORDER_CANCEL = 'api/v5/trade/cancel-order'
OKEX_BATCH_ORDER_CANCEL = 'api/v5/trade/cancel-batch-orders'
OKEX_BALANCE_URL = 'api/v5/account/balance'
OKEX_FEE_URL = 'api/v5/account/trade-fee?instType={instType}&instId={trading_pair}'


# WS
OKEX_WS_URI_PUBLIC = "wss://ws.okex.com:8443/ws/v5/public"
OKEX_WS_URI_PRIVATE = "wss://ws.okex.com:8443/ws/v5/private"

OKEX_WS_CHANNEL_ACCOUNT = "account"
OKEX_WS_CHANNEL_ORDERS = "orders"

OKEX_WS_CHANNELS = {
    OKEX_WS_CHANNEL_ACCOUNT,
    OKEX_WS_CHANNEL_ORDERS
}
