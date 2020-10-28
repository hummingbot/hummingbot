from urllib.parse import urljoin


# URLs

OKEX_BASE_URL = "https://www.okex.com/"


OKEX_SYMBOLS_URL = urljoin(OKEX_BASE_URL, "api/spot/v3/instruments/ticker")
OKEX_DEPTH_URL = urljoin(OKEX_BASE_URL, "api/spot/v3/instruments/{trading_pair}/book")
OKEX_PRICE_URL = urljoin(OKEX_BASE_URL, 'api/spot/v3/instruments/{trading_pair}/ticker')

# Doesn't include base URL as the tail is required to generate the signature

OKEX_SERVER_TIME = 'api/general/v3/time'
OKEX_INSTRUMENTS_URL = "api/spot/v3/instruments"

# Auth required

OKEX_PLACE_ORDER = "api/spot/v3/orders"
OKEX_ORDER_DETAILS_URL = 'api/spot/v3/orders/{exchange_order_id}'
OKEX_ORDER_CANCEL = 'api/spot/v3/cancel_orders/{exchange_order_id}'
OKEX_BATCH_ORDER_CANCELL = 'api/spot/v3/cancel_batch_orders'
OKEX_BALANCE_URL = "api/spot/v3/accounts"


# WS
OKEX_WS_URI = "wss://real.okex.com:8443/ws/v3"

OKEX_WS_CHANNEL_SPOT_ACCOUNT = "spot/account"
OKEX_WS_CHANNEL_SPOT_ORDER = "spot/order"

OKEX_WS_CHANNELS = {
    OKEX_WS_CHANNEL_SPOT_ACCOUNT,
    OKEX_WS_CHANNEL_SPOT_ORDER
}


# OKEx statuses

ORDER_STATUSES = {
    -2: 'Failed',
    -1: 'Canceled',
    0: 'open',
    1: 'partially filled',
    2: 'fullyfilled',
    3: 'submitting',
    4: 'canceling'
}


# Order Status: -2 = Failed -1 = Canceled 0 = Open 1 = Partially Filled 2 = Fully Filled 3 = Submitting 4 = Canceling
