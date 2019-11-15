class Constants:
    """
    Constants class stores all of the constants required for Liquid connector module
    """

    # Rest API endpoints
    BASE_URL = 'https://api.liquid.com'

    GET_EXCHANGE_MARKETS_URL = BASE_URL + '/products'
    GET_SNAPSHOT_URL = BASE_URL + '/products/{id}/price_levels?full={full}'

    # Web socket endpoints
    BAEE_WS_URL = 'wss://tap.liquid.com/app/LiquidTapClient'
    WS_ORDER_BOOK_DIFF_SUBSCRIPTION = 'price_ladders_cash_{currency_pair_code}_{side}'

    # Web socket others
    WS_PUSHER_SUBSCRIBE_STR = 'pusher:subscribe'

    # Timeouts
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    # Others
    SIDE_BID = 'buy'
    SIDE_ASK = 'sell'
