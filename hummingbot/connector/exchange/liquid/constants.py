class Constants:
    """
    Constants class stores all of the constants required for Liquid connector module
    """

    # Rest API endpoints
    BASE_URL = 'https://api.liquid.com'

    # GET
    PRODUCTS_URI = '/products'
    ACCOUNTS_BALANCE_URI = '/accounts/balance'
    CRYPTO_ACCOUNTS_URI = '/crypto_accounts'
    FIAT_ACCOUNTS_URI = '/fiat_accounts'
    LIST_ORDER_URI = '/orders/{exchange_order_id}'
    LIST_ORDERS_URI = '/orders?with_details=1'
    TRADING_RULES_URI = '/currencies'

    # POST
    ORDER_CREATION_URI = '/orders'

    # PUT
    CANCEL_ORDER_URI = '/orders/{exchange_order_id}/cancel'

    GET_EXCHANGE_MARKETS_URL = BASE_URL + PRODUCTS_URI
    GET_SNAPSHOT_URL = BASE_URL + '/products/{id}/price_levels?full={full}'

    # Web socket endpoints
    BAEE_WS_URL = 'wss://tap.liquid.com/app/LiquidTapClient'
    WS_REQUEST_PATH = '/realtime'
    WS_ORDER_BOOK_DIFF_SUBSCRIPTION = 'price_ladders_cash_{currency_pair_code}_{side}'
    WS_USER_TRADES_SUBSCRIPTION = 'user_account_{funding_currency}_trades'
    WS_USER_EXECUTIONS_SUBSCRIPTION = 'user_executions_cash_{currency_pair_code}'
    WS_USER_ACCOUNTS_SUBSCRIPTION = 'user_account_{quoted_currency}_orders'

    # Web socket events
    WS_AUTH_REQUEST_EVENT = 'quoine:auth_request'
    WS_PUSHER_SUBSCRIBE_EVENT = 'pusher:subscribe'

    # Timeouts
    MESSAGE_TIMEOUT = 90.0
    PING_TIMEOUT = 10.0

    API_CALL_TIMEOUT = 10.0
    UPDATE_ORDERS_INTERVAL = 10.0

    # Others
    SIDE_BID = 'buy'
    SIDE_ASK = 'sell'

    DEFAULT_ASSETS_PRECISION = 2
    DEFAULT_QUOTING_PRECISION = 8
