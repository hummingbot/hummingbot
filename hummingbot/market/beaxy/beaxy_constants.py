class BeaxyConstants:
    class TradingApi:
        BASE_URL = "https://test-tradingapi.tokenexus.com"
        LOGIN_ATTEMT_ENDPOINT = "/api/v1/login/attempt"
        LOGIN_CONFIRM_ENDPOINT = "/api/v1/login/confirm"

    class PublicApi:
        BASE_URL = "https://services.beaxy.com"
        SYMBOLS_URL = BASE_URL + "/api/v2/symbols"
        RATES_URL = BASE_URL + "/api/v2/symbols/rates"
        ORDER_BOOK_URL = BASE_URL + "/api/v2/symbols/{symbol}/book?depth={depth}"
        WS_BASE_URL = "wss://services.beaxy.com/ws/v2"
