from urllib.parse import urljoin


# URLs

OKEX_BASE_URL = "https://www.okex.com/"


OKEX_SYMBOLS_URL = urljoin(OKEX_BASE_URL, "api/spot/v3/instruments/ticker")
OKEX_DEPTH_URL = urljoin(OKEX_BASE_URL, "api/spot/v3/instruments/{trading_pair}/book")

# Doesn't include base URL as the tail is required to generate the signature

OKEX_SERVER_TIME = 'api/general/v3/time'

# Auth required

OKEX_PLACE_ORDER = "api/spot/v3/orders"
OKEX_ORDER_DETAILS_URL = 'api/spot/orders/{exchange_order_id}'
OKEX_BATCH_ORDER_CANCELL = 'api/spot/v3/cancel_batch_orders'
OKEX_BALANCE_URL = "api/spot/v3/accounts"
OKEX_INSTRUMENTS_URL = "api/spot/v3/instruments"


# WS
OKCOIN_WS_URI = "wss://real.okex.com:8443/ws/v3"

# OKEx statuses

ORDER_STATUSES = {
    -2: 'Failed',
    -1: 'Canceled',
    0: 'open',
    1: 'partially filled',
    2: 'fullyfilled',
    3:  'submitting',
    4:  'canceling'
}


# Order Status: -2 = Failed -1 = Canceled 0 = Open 1 = Partially Filled 2 = Fully Filled 3 = Submitting 4 = Canceling