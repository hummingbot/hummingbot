# -*- coding: utf-8 -*-


class BeaxyConstants:
    class TradingApi:
        BASE_URL_V1 = 'https://tradingapi.beaxy.com'
        BASE_URL = 'https://tradewith.beaxy.com'
        HEALTH_ENDPOINT = '/api/v2/health'
        TOKEN_ENDPOINT = '/api/v2/auth'
        WALLETS_ENDPOINT = '/api/v2/wallets'
        OPEN_ORDERS_ENDPOINT = '/api/v2/orders/open'
        CLOSED_ORDERS_ENDPOINT = '/api/v2/orders/closed?from_date={from_date}'
        DELETE_ORDER_ENDPOINT = '/api/v2/orders/open/{id}'
        CREATE_ORDER_ENDPOINT = '/api/v2/orders'
        TRADE_SETTINGS_ENDPOINT = '/api/v2/tradingsettings'

        LOGIN_ATTEMT_ENDPOINT = '/api/v1/login/attempt'
        LOGIN_CONFIRM_ENDPOINT = '/api/v1/login/confirm'

        WS_BASE_URL = 'wss://tradingapi.beaxy.com/websocket/v1'

    class PublicApi:
        BASE_URL = 'https://services.beaxy.com'
        SYMBOLS_URL = BASE_URL + '/api/v2/symbols'
        RATE_URL = BASE_URL + '/api/v2/symbols/{symbol}/rate'
        RATES_URL = BASE_URL + '/api/v2/symbols/rates'
        ORDER_BOOK_URL = BASE_URL + '/api/v2/symbols/{symbol}/book?depth={depth}'

        WS_BASE_URL = 'wss://services.beaxy.com/ws/v2'
