class FixtureBittrex:
    PING = {"serverTime": 1582535502000}

    MARKETS = [
        {
            "symbol": "ETH-BTC", "baseCurrencySymbol": "ETH", "quoteCurrencySymbol": "BTC",
            "minTradeSize": "0.01314872", "precision": 8,
            "status": "ONLINE", "createdAt": "2015-08-14T09:02:24.817Z"},
        {
            "symbol": "BTC-USDT", "baseCurrencySymbol": "BTC", "quoteCurrencySymbol": "USDT",
            "minTradeSize": "0.00025334", "precision": 8,
            "status": "ONLINE", "createdAt": "2015-12-11T06:31:40.633Z", "notice": ""},
        {
            "symbol": "BTC-USD", "baseCurrencySymbol": "BTC", "quoteCurrencySymbol": "USD",
            "minTradeSize": "0.00025427", "precision": 3,
            "status": "ONLINE", "createdAt": "2018-05-31T13:24:40.77Z"},
        {
            "symbol": "ETH-USDT", "baseCurrencySymbol": "ETH", "quoteCurrencySymbol": "USDT",
            "minTradeSize": "0.01334966", "precision": 8,
            "status": "ONLINE", "createdAt": "2017-04-20T17:26:37.647Z", "notice": ""}
    ]

    MARKETS_TICKERS = [
        {
            "symbol": "ETH-BTC", "lastTradeRate": "0.02739396",
            "bidRate": "0.02740726", "askRate": "0.02741416"},
        {
            "symbol": "ETH-USDT", "lastTradeRate": "267.26100000",
            "bidRate": "266.96646649", "askRate": "267.22586512"},
        {
            "symbol": "BTC-USDT", "lastTradeRate": "9758.81200003",
            "bidRate": "9760.51000000", "askRate": "9765.82533436"},
        {
            "symbol": "BTC-USD", "lastTradeRate": "9770.73200000",
            "bidRate": "9767.64400000", "askRate": "9770.73200000"}
    ]

    # General User Info
    BALANCES = [{"currencySymbol": "BTC", "total": "0.00279886", "available": "0.00279886"},
                {"currencySymbol": "BTXCRD", "total": "1031.33915356", "available": "1031.33915356"},
                {"currencySymbol": "ETH", "total": "0.24010276", "available": "0.24010276"},
                {"currencySymbol": "USDT", "total": "76.30113330", "available": "67.48856276"},
                {"currencySymbol": "XZC", "total": "4.99205590", "available": "4.99205590"},
                {"currencySymbol": "ZRX", "total": "0.00000000", "available": "0.00000000"}]

    # User Trade Info
    FILLED_BUY_LIMIT_ORDER = {
        "id": "d7850281-0440-4478-879f-248499b2134d", "marketSymbol": "ETH-USDT", "direction": "BUY",
        "type": "LIMIT", "quantity": "0.06000000", "limit": "268.09208274",
        "timeInForce": "GOOD_TIL_CANCELLED", "fillQuantity": "0.06000000", "commission": "0.01333791",
        "proceeds": "5.33516582", "status": "CLOSED", "createdAt": "2020-02-24T09:38:13.1Z",
        "updatedAt": "2020-02-24T09:38:13.1Z", "closedAt": "2020-02-24T09:38:13.1Z"}

    OPEN_BUY_LIMIT_ORDER = {
        "id": "615aa7de-3ff9-486d-98d7-2d37aca212c9", "marketSymbol": "ETH-USDT", "direction": "BUY",
        "type": "LIMIT", "quantity": "0.06000000", "limit": "205.64319999",
        "timeInForce": "GOOD_TIL_CANCELLED", "fillQuantity": "0.00000000", "commission": "0.00000000",
        "proceeds": "0.00000000", "status": "OPEN", "createdAt": "2020-02-25T11:13:32.12Z",
        "updatedAt": "2020-02-25T11:13:32.12Z"}

    CANCEL_ORDER = {
        "id": "615aa7de-3ff9-486d-98d7-2d37aca212c9", "marketSymbol": "ETH-USDT", "direction": "BUY",
        "type": "LIMIT", "quantity": "0.06000000", "limit": "205.64319999",
        "timeInForce": "GOOD_TIL_CANCELLED", "fillQuantity": "0.00000000", "commission": "0.00000000",
        "proceeds": "0.00000000", "status": "CLOSED", "createdAt": "2020-02-25T11:13:32.12Z",
        "updatedAt": "2020-02-25T11:13:33.63Z", "closedAt": "2020-02-25T11:13:33.63Z"}

    ORDERS_OPEN = [
        {
            "id": "9854dc2a-0762-408d-922f-882f4359c517", "marketSymbol": "ETH-USDT", "direction": "BUY", "type": "LIMIT",
            "quantity": "0.03000000", "limit": "134.75247524", "timeInForce": "GOOD_TIL_CANCELLED",
            "fillQuantity": "0.00000000", "commission": "0.00000000", "proceeds": "0.00000000", "status": "OPEN",
            "createdAt": "2020-01-10T10:25:25.13Z", "updatedAt": "2020-01-10T10:25:25.13Z"},
        {
            "id": "261d9158-c9c1-40a6-bad8-4b447a471d8f", "marketSymbol": "ETH-USDT", "direction": "BUY", "type": "LIMIT",
            "quantity": "0.03000000", "limit": "158.26732673", "timeInForce": "GOOD_TIL_CANCELLED",
            "fillQuantity": "0.00000000", "commission": "0.00000000", "proceeds": "0.00000000", "status": "OPEN",
            "createdAt": "2020-01-26T02:58:14.19Z", "updatedAt": "2020-01-26T02:58:14.19Z"}
    ]

    WS_AFTER_BUY_2 = {
        'event_type': 'uO', 'content': {
            'w': 'f8907116-4e24-4602-b691-d110b5ce1bf8', 'N': 8, 'TY': 2,
            'o': {
                'U': '00000000-0000-0000-0000-000000000000',
                'I': 4551095126,
                'OU': 'd67c837e-56c5-41e2-b65b-fe590eb06eaf',
                'E': 'ETH-USDT', 'OT': 'LIMIT_BUY', 'Q': 0.06, 'q': 0.0,
                'X': 269.05759499, 'n': 0.01338594, 'P': 5.35437999,
                'PU': 267.7189995, 'Y': 1582540341630,
                'C': 1582540341630, 'i': False, 'CI': False, 'K': False,
                'k': False, 'J': None, 'j': None, 'u': 1582540341630,
                'PassthroughUuid': None}},
        'error': None,
        'time': '2020-02-24T10:32:21'
    }

    WS_AFTER_BUY_1 = {
        'event_type': 'uO', 'content': {
            'w': 'f8907116-4e24-4602-b691-d110b5ce1bf8', 'N': 13, 'TY': 0,
            'o': {
                'U': '00000000-0000-0000-0000-000000000000', 'I': 4564385840,
                'OU': '615aa7de-3ff9-486d-98d7-2d37aca212c9', 'E': 'ETH-USDT',
                'OT': 'LIMIT_BUY', 'Q': 0.06, 'q': 0.06, 'X': 205.64319999, 'n': 0.0,
                'P': 0.0, 'PU': 0.0, 'Y': 1582629212120, 'C': None, 'i': True,
                'CI': False, 'K': False, 'k': False, 'J': None, 'j': None,
                'u': 1582629212120, 'PassthroughUuid': None}},
        'error': None,
        'time': '2020-02-25T11:13:32'
    }

    WS_AFTER_SELL_2 = {
        'event_type': 'uO',
        'content': {
            'w': 'f8907116-4e24-4602-b691-d110b5ce1bf8', 'N': 10, 'TY': 2,
            'o': {
                'U': '00000000-0000-0000-0000-000000000000', 'I': 4279414326,
                'OU': '447256cc-9335-41f3-bec9-7392804d30cd', 'E': 'ETH-USDT',
                'OT': 'LIMIT_SELL', 'Q': 0.06, 'q': 0.0, 'X': 257.72689, 'n': 0.0129511,
                'P': 5.18044, 'PU': 259.022, 'Y': 1582627522640, 'C': 1582627522640,
                'i': False, 'CI': False, 'K': False, 'k': False, 'J': None, 'j': None,
                'u': 1582627522640, 'PassthroughUuid': None}},
        'error': None,
        'time': '2020-02-25T10:45:22'}

    WS_ORDER_BOOK_SNAPSHOT = {
        'nonce': 115097,
        'type': 'snapshot',
        'results': {
            'M': 'ETH-USDT', 'N': 115097,
            'Z': [
                {'Q': 3.7876, 'R': 261.805},
                {'Q': 3.99999998, 'R': 261.80200001},
                {'Q': 20.92267278, 'R': 261.75575521}],
            'S': [
                {'Q': 3.618, 'R': 262.06976758},
                {'Q': 1.2, 'R': 262.06976759},
                {'Q': 4.0241, 'R': 262.07}],
            'f': [
                {'I': 53304378, 'T': 1582604545290, 'Q': 1.75736397, 'P': 261.83, 't': 460.1306082651,
                 'F': 'FILL', 'OT': 'SELL', 'U': 'a0de16e3-6f6d-43f0-b9ea-a8c1f9835223'},
                {'I': 53304377, 'T': 1582604544910, 'Q': 0.42976603, 'P': 261.83, 't': 112.5256396349,
                 'F': 'FILL', 'OT': 'SELL', 'U': 'dc723d5e-2af5-4010-9eb2-a915f050015e'}]}
    }
