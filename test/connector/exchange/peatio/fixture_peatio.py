class FixturePeatio:
    LIMIT_MAKER_ERROR = {'status': 'error', 'err-code': 'order-invalid-price', 'err-msg': 'invalid price', 'data': None}

    BALANCES = [
        {
            'currency': 'mdt-erc20',
            'balance': '0.0',
            'locked': '0.0',
            'deposit_address': {
                'currencies': [
                    'mdt-erc20',
                    'uni-erc20',
                    'eth',
                    'usdt-erc20',
                    'mcr-erc20',
                    'usdc-erc20',
                    'dai-erc20'
                ],
                'address': '0x0f6c962daef32f5d7d611f38058d8a1e2579393b',
                'state': 'active'
            }
        },
        {
            'currency': 'eth',
            'balance': '100.0',
            'locked': '0.0',
            'deposit_address': {
                'currencies': [
                    'mdt-erc20',
                    'uni-erc20',
                    'eth',
                    'usdt-erc20',
                    'mcr-erc20',
                    'usdc-erc20',
                    'dai-erc20'
                ],
                'address': '0x0f6c962daef32f5d7d611f38058d8a1e2579393b',
                'state': 'active'
            }
        },
        {
            'currency': 'usdt-erc20',
            'balance': '3000.0',
            'locked': '0.0',
            'deposit_address': {
                'currencies': [
                    'mdt-erc20',
                    'uni-erc20',
                    'eth',
                    'usdt-erc20',
                    'mcr-erc20',
                    'usdc-erc20',
                    'dai-erc20'
                ],
                'address': '0x0f6c962daef32f5d7d611f38058d8a1e2579393b',
                'state': 'active'
            }
        },
        {
            'currency': 'mcr-erc20',
            'balance': '0.0',
            'locked': '0.0',
            'deposit_address': {
                'currencies': [
                    'mdt-erc20',
                    'uni-erc20',
                    'eth',
                    'usdt-erc20',
                    'mcr-erc20',
                    'usdc-erc20',
                    'dai-erc20'
                ],
                'address': '0x0f6c962daef32f5d7d611f38058d8a1e2579393b',
                'state': 'active'
            }
        },
    ]

    ORDER_PLACE = {
        'id': 3934044,
        'uuid': '2d4df661-76d8-41fa-a714-860aaaac2eac',
        'side': 'sell',
        'ord_type': 'limit',
        'price': '100000.0',
        'avg_price': '0.0',
        'state': 'wait',
        'market': 'eth_usdterc20',
        'market_type': 'spot',
        'created_at': '2021-08-20T06:53:35Z',
        'updated_at': '2021-08-20T06:53:35Z',
        'origin_volume': '0.0027',
        'remaining_volume': '0.0027',
        'executed_volume': '0.0',
        'maker_fee': '0.002',
        'taker_fee': '0.002',
        'trades_count': 0
    }

    FILLED_BUY_LIMIT_ORDER = {
        "status": "ok",
        "data": {
            "id": 69092298194, "symbol": "ethusdt", "account-id": 11899168,
            "client-order-id": "buy-ethusdt-1581561936007620",
            "amount": "0.060000000000000000", "price": "286.850000000000000000",
            "created-at": 1581561936082, "type": "buy-limit",
            "field-amount": "0.060000000000000000",
            "field-cash-amount": "5.464200000000000000",
            "field-fees": "0.000040000000000000", "finished-at": 1581561936222,
            "source": "spot-api", "state": "filled", "canceled-at": 0}}

    FILLED_SELL_LIMIT_ORDER = {
        "status": "ok",
        "data": {
            "id": 69094165877, "symbol": "ethusdt", "account-id": 11899168,
            "client-order-id": "sell-ethusdt-1581562860006536",
            "amount": "0.060000000000000000",
            "price": "259.110000000000000000", "created-at": 1581562860124,
            "type": "sell-limit", "field-amount": "0.060000000000000000",
            "field-cash-amount": "5.455400000000000000",
            "field-fees": "0.010910800000000000", "finished-at": 1581562860240,
            "source": "spot-api", "state": "filled", "canceled-at": 0}}

    BUY_MARKET_ORDER = {
        'id': 4037206,
        'uuid': 'c5c7dbdb-6e98-44e9-94c5-b82b3f68766e',
        'side': 'sell',
        'ord_type': 'limit',
        'price': '3800.0',
        'avg_price': '0.0',
        'state': 'wait',
        'market': 'eth_usdterc20',
        'market_type': 'spot',
        'created_at': '2021-09-07T13:55:39Z',
        'updated_at': '2021-09-07T13:55:39Z',
        'origin_volume': '0.0162',
        'remaining_volume': '0.0162',
        'executed_volume': '0.0',
        'maker_fee': '0.002',
        'taker_fee': '0.002',
        'trades_count': 0,
        'trades': []
    }

    TRADE = {
        'id': 183513,
        'price': 3753.9396,
        'amount': 0.005,
        'total': 18.769698,
        'market': 'eth_usdterc20',
        'created_at': 1631015195,
        'taker_type': 'sell'
    }

    SELL_MARKET_ORDER = {
        "status": "ok", "data": {
            "id": 69095353390, "symbol": "ethusdt", "account-id": 11899168,
            "client-order-id": "sell-ethusdt-1581563456004786",
            "amount": "0.060000000000000000", "price": "0.0",
            "created-at": 1581563456081, "type": "sell-market",
            "field-amount": "0.060000000000000000",
            "field-cash-amount": "5.459200000000000000",
            "field-fees": "0.010918400000000000",
            "finished-at": 1581563456183, "source": "spot-api",
            "state": "filled", "canceled-at": 0}}

    OPEN_BUY_LIMIT_ORDER = {
        "status": "ok",
        "data": {
            "id": 69095996284, "symbol": "ethusdt", "account-id": 11899168,
            "client-order-id": "buy-ethusdt-1581563740035369",
            "amount": "0.060000000000000000", "price": "244.640000000000000000",
            "created-at": 1581563742607, "type": "buy-limit", "field-amount": "0.0",
            "field-cash-amount": "0.0", "field-fees": "0.0", "finished-at": 0,
            "source": "spot-api", "state": "submitted", "canceled-at": 0}}

    OPEN_SELL_LIMIT_ORDER = {
        "status": "ok",
        "data": {
            "id": 69095996284, "symbol": "ethusdt", "account-id": 11899168,
            "client-order-id": "buy-ethusdt-1581563740035369",
            "amount": "0.060000000000000000", "price": "244.640000000000000000",
            "created-at": 1581563742607, "type": "sell-limit", "field-amount": "0.0",
            "field-cash-amount": "0.0", "field-fees": "0.0", "finished-at": 0,
            "source": "spot-api", "state": "submitted", "canceled-at": 0}}

    CANCEL_ORDER = {
        "status": "ok",
        "data": {
            "id": 69095996284, "symbol": "ethusdt", "account-id": 11899168,
            "client-order-id": "buy-ethusdt-1581563740035369",
            "amount": "0.060000000000000000", "price": "244.640000000000000000",
            "created-at": 1581563742607, "type": "buy-limit",
            "field-amount": "0.0", "field-cash-amount": "0.0",
            "field-fees": "0.0", "finished-at": 1581563762817,
            "source": "spot-api", "state": "canceled",
            "canceled-at": 1581563762755}}

    ORDERS_BATCH_CANCELLED = {"status": "ok", "data": {"success": ["69098120228", "69098120253"], "failed": []}}

    MARKET_TICKERS = {
        'btc_usdterc20': {
            'at': '1631594064',
            'ticker': {
                'at': '1631594064',
                'avg_price': '0.0',
                'high': '0.0',
                'last': '51013.9034',
                'low': '0.0',
                'open': '0.0',
                'price_change_percent': '+0.00%',
                'volume': '0.0',
                'amount': '0.0'
            }
        },
        'eth_usdterc20': {
            'at': '1631594067',
            'ticker': {
                'at': '1631594067',
                'avg_price': '0.0',
                'high': '0.0',
                'last': '3744.0',
                'low': '0.0',
                'open': '0.0',
                'price_change_percent': '+0.00%',
                'volume': '0.0',
                'amount': '0.0'
            }
        }
    }

    ORDER_BOOKS = {
        'asks': [
            {
                'id': 4037206,
                'uuid': 'c5c7dbdb-6e98-44e9-94c5-b82b3f68766e',
                'side': 'sell',
                'ord_type': 'limit',
                'price': '3800.0',
                'avg_price': '0.0',
                'state': 'wait',
                'market': 'eth_usdterc20',
                'market_type': 'spot',
                'created_at': '2021-09-07T13:55:39Z',
                'updated_at': '2021-09-07T13:55:39Z',
                'origin_volume': '0.0162',
                'remaining_volume': '0.0162',
                'executed_volume': '0.0',
                'maker_fee': '0.002',
                'taker_fee': '0.002',
                'trades_count': 0
            },
        ],
        'bids': [
            {
                'id': 4037298,
                'uuid': '80084a11-f85a-423e-9efd-69c9fe60106a',
                'side': 'buy',
                'ord_type': 'limit',
                'price': '3700.0',
                'avg_price': '0.0',
                'state': 'wait',
                'market': 'eth_usdterc20',
                'market_type': 'spot',
                'created_at': '2021-09-07T13:55:39Z',
                'updated_at': '2021-09-07T13:55:39Z',
                'origin_volume': '0.1',
                'remaining_volume': '0.1',
                'executed_volume': '0.0',
                'maker_fee': '0.002',
                'taker_fee': '0.002',
                'trades_count': 0
            }
        ]
    }
