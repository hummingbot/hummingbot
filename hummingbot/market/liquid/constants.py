class Constants:
    """
    Constants class stores all of the constants required for Liquid connector module
    """

    # Rest API endpoints
    BASE_URL = 'https://api.liquid.com'

    GET_EXCHANGE_MARKETS_URL = BASE_URL + '/products'
    GET_SNAPSHOT_URL = BASE_URL + '/products/{id}/price_levels?full={full}'

    # Timeouts
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0