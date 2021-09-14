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
        "status": "ok", "data": {
            "id": 69094699396, "symbol": "ethusdt", "account-id": 11899168,
            "client-order-id": "buy-ethusdt-1581563124007518",
            "amount": "5.460000000000000000", "price": "0.0",
            "created-at": 1581563124085, "type": "buy-market",
            "field-amount": "0.060015396458814472",
            "field-cash-amount": "5.459999999999999816",
            "field-fees": "0.000040030792917629", "finished-at": 1581563124185,
            "source": "spot-api", "state": "filled", "canceled-at": 0}}

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
