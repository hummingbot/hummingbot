from aiohttp import web


class PeatioMockAPI:
    MOCK_PEATIO_USER_ID = 10000000
    MOCK_PEATIO_LIMIT_BUY_ORDER_ID = 11111
    MOCK_PEATIO_LIMIT_BUY_ORDER_SIDE = "buy"
    MOCK_PEATIO_LIMIT_BUY_ORDER_TYPE = "limit"

    MOCK_PEATIO_LIMIT_SELL_ORDER_ID = 22222
    MOCK_PEATIO_LIMIT_SELL_ORDER_SIDE = "sell"
    MOCK_PEATIO_LIMIT_SELL_ORDER_TYPE = "limit"

    MOCK_PEATIO_MARKET_BUY_ORDER_ID = 33333
    MOCK_PEATIO_MARKET_BUY_ORDER_SIDE = "buy"
    MOCK_PEATIO_MARKET_BUY_ORDER_TYPE = "limit"

    MOCK_PEATIO_MARKET_SELL_ORDER_ID = 44444
    MOCK_PEATIO_MARKET_SELL_ORDER_SIDE = "sell"
    MOCK_PEATIO_MARKET_SELL_ORDER_TYPE = "market"

    MOCK_PEATIO_LIMIT_CANCEL_ORDER_ID = 55555
    MOCK_PEATIO_LIMIT_OPEN_ORDER_ID = 66666
    MOCK_PEATIO_LIMIT_BUY_RESPONSE = {
        "status": "ok",
        "data": {
            "id": MOCK_PEATIO_LIMIT_BUY_ORDER_ID,
            "symbol": "ethusdt",
            "account-id": 10055506,
            "amount": "0.020000000000000000",
            "price": "189.770000000000000000",
            "created-at": 1570494069606,
            "type": "buy-limit",
            "field-amount": "0.020000000000000000",
            "field-cash-amount": "3.614600000000000000",
            "field-fees": "0.000040000000000000",
            "finished-at": 1570494069689,
            "user-id": MOCK_PEATIO_USER_ID,
            "source": "spot-api",
            "state": "filled",
            "canceled-at": 0
        }
    }
    MOCK_PEATIO_LIMIT_SELL_RESPONSE = {
        "status": "ok",
        "data": {
            "id": MOCK_PEATIO_LIMIT_SELL_ORDER_ID,
            "symbol": "ethusdt",
            "account-id": 10055506,
            "amount": "0.020000000000000000",
            "price": "189.770000000000000000",
            "created-at": 1570494069606,
            "type": "sell-limit",
            "field-amount": "0.020000000000000000",
            "field-cash-amount": "3.614600000000000000",
            "field-fees": "0.000040000000000000",
            "finished-at": 1570494069689,
            "user-id": MOCK_PEATIO_USER_ID,
            "source": "spot-api",
            "state": "filled",
            "canceled-at": 0
        }
    }
    MOCK_PEATIO_MARKET_BUY_RESPONSE = {
        "status": "ok",
        "data": {
            "id": MOCK_PEATIO_LIMIT_BUY_ORDER_ID,
            "symbol": "ethusdt",
            "account-id": 10055506,
            "amount": "3.580000000000000000",
            "price": "0.0",
            "created-at": 1570571586091,
            "type": "buy-market",
            "field-amount": "0.020024611254055263",
            "field-cash-amount": "3.579999999999999919",
            "field-fees": "0.000040049222508111",
            "finished-at": 1570571586178,
            "source": "spot-api",
            "state": "filled",
            "canceled-at": 0
        }
    }
    MOCK_PEATIO_MARKET_SELL_RESPONSE = {
        "status": "ok",
        "data": {
            "id": MOCK_PEATIO_MARKET_SELL_ORDER_ID,
            "symbol": "ethusdt",
            "account-id": 10055506,
            "amount": "0.020000000000000000",
            "price": "0.0",
            "created-at": 1570494069606,
            "type": "sell-market",
            "field-amount": "0.020000000000000000",
            "field-cash-amount": "3.614600000000000000",
            "field-fees": "0.000040000000000000",
            "finished-at": 1570494069689,
            "user-id": MOCK_PEATIO_USER_ID,
            "source": "spot-api",
            "state": "filled",
            "canceled-at": 0
        }
    }
    MOCK_PEATIO_LIMIT_CANCEL_RESPONSE = {
        "status": "ok",
        "data": {
            "id": MOCK_PEATIO_LIMIT_CANCEL_ORDER_ID,
            "symbol": "ethusdt",
            "account-id": 10055506,
            "amount": "0.020000000000000000",
            "price": "162.670000000000000000",
            "created-at": 1570575422098,
            "type": "buy-limit",
            "field-amount": "0.0",
            "field-cash-amount": "0.0",
            "field-fees": "0.0",
            "finished-at": 1570575423650,
            "source": "spot-api",
            "state": "submitted",
            "canceled-at": 1570575423600
        }
    }
    MOCK_PEATIO_LIMIT_OPEN_RESPONSE = {
        "status": "ok",
        "data": {
            "id": MOCK_PEATIO_LIMIT_OPEN_ORDER_ID,
            "symbol": "ethusdt",
            "account-id": 10055506,
            "amount": "0.040000000000000000",
            "price": "162.670000000000000000",
            "created-at": 1570575422098,
            "type": "buy-limit",
            "field-amount": "0.0",
            "field-cash-amount": "0.0",
            "field-fees": "0.0",
            "finished-at": 1570575423650,
            "source": "spot-api",
            "state": "submitted",
            "canceled-at": 1570575423600
        }
    }

    def __init__(self):
        self.order_id = None
        self.order_side = 'sell'
        self.order_type = 'limit'
        self.order_price = '100000.0'
        self.order_volume = '0.0027'
        self.order_market = 'eth_usdterc20'

        self.cancel_all_order_ids = []
        self.order_response_dict = {
            self.MOCK_PEATIO_LIMIT_BUY_ORDER_ID: self.MOCK_PEATIO_LIMIT_BUY_RESPONSE,
            self.MOCK_PEATIO_LIMIT_SELL_ORDER_ID: self.MOCK_PEATIO_LIMIT_SELL_RESPONSE,
            self.MOCK_PEATIO_MARKET_BUY_ORDER_ID: self.MOCK_PEATIO_MARKET_BUY_RESPONSE,
            self.MOCK_PEATIO_MARKET_SELL_ORDER_ID: self.MOCK_PEATIO_MARKET_SELL_RESPONSE,
            self.MOCK_PEATIO_LIMIT_CANCEL_ORDER_ID: self.MOCK_PEATIO_LIMIT_CANCEL_RESPONSE,
            self.MOCK_PEATIO_LIMIT_OPEN_ORDER_ID: self.MOCK_PEATIO_LIMIT_OPEN_RESPONSE
        }

    async def get_mock_snapshot(self, _):
        return web.json_response({
            "ch": "market.ethusdt.depth.step0",
            "ts": 1570486543309,
            "tick": {
                "bids": [
                    [
                        100.21,
                        23.5445
                    ],
                    [
                        100.2,
                        86.4019
                    ],
                    [
                        100.17,
                        6.1261
                    ],
                    [
                        100.16,
                        10.0
                    ],
                    [
                        100.14,
                        8.0
                    ]
                ],
                "asks": [
                    [
                        100.24,
                        2.3602
                    ],
                    [
                        100.25,
                        15.1513
                    ],
                    [
                        100.27,
                        19.1565
                    ],
                    [
                        100.29,
                        12.0
                    ],
                    [
                        100.3,
                        23.3643
                    ]
                ],
                "version": 102339771356,
                "ts": 1570486543009
            }
        })

    async def get_market_tickers(self, _):
        response = {
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
        return web.json_response(response, status=200)

    async def get_account_accounts(self, _):
        response = {
            "status": "ok",
            "data": [{
                "id": self.MOCK_PEATIO_USER_ID,
                "type": "spot",
                "subtype": "",
                "state": "working"
            }]
        }
        return web.json_response(response, status=200)

    async def get_common_timestamp(self, _):
        response = "2021-09-14T04:39:13+00:00"
        return web.json_response(response, status=200)

    async def get_common_symbols(self, _):
        response = [
            {
                'id': 'btc_usdterc20',
                'symbol': 'btc_usdterc20',
                'name': 'BTC/USDT-ERC20',
                'type': 'spot',
                'base_unit': 'btc',
                'quote_unit': 'usdt-erc20',
                'min_price': '20000.0',
                'max_price': '0.0',
                'min_amount': '0.0003',
                'amount_precision': 4,
                'price_precision': 4,
                'state': 'enabled'},
            {
                'id': 'eth_usdterc20',
                'symbol': 'eth_usdterc20',
                'name': 'ETH/USDT-ERC20',
                'type': 'spot',
                'base_unit': 'eth',
                'quote_unit': 'usdt-erc20',
                'min_price': '1300.0',
                'max_price': '0.0',
                'min_amount': '0.003',
                'amount_precision': 4,
                'price_precision': 4,
                'state': 'enabled'
            },
        ]
        return web.json_response(response, status=200)

    async def get_user_balance(self, _):
        response = [
            {
                'currency': 'usdt-erc20',
                'balance': '0.0',
                'locked': '0.0',
                'deposit_address': {
                    'currencies': [
                        'usdt-erc20',
                        'eth',
                        'mdt-erc20',
                        'uni-erc20',
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
                'balance': '0.259942948171422263',
                'locked': '0.0',
                'deposit_address': {
                    'currencies': [
                        'usdt-erc20',
                        'eth',
                        'mdt-erc20',
                        'uni-erc20',
                        'mcr-erc20',
                        'usdc-erc20',
                        'dai-erc20'
                    ],
                    'address': '0x0f6c962daef32f5d7d611f38058d8a1e2579393b',
                    'state': 'active'
                }
            },
            {
                'currency': 'btc',
                'balance': '0.0',
                'locked': '0.0',
                'enable_invoice': True
            },
        ]
        return web.json_response(response, status=200)

    async def post_order_place(self, req: web.Request):
        response = {
            'id': self.order_id,
            'uuid': '2d4df661-76d8-41fa-a714-860aaaac2eac',
            'side': self.order_side,
            'ord_type': self.order_type,
            'price': self.order_price,
            'avg_price': '0.0',
            'state': 'wait',
            'market': self.order_market,
            'market_type': 'spot',
            'created_at': '2021-08-20T06:53:35Z',
            'updated_at': '2021-08-20T06:53:35Z',
            'origin_volume': self.order_volume,
            'remaining_volume': self.order_volume,
            'executed_volume': '0.0',
            'maker_fee': '0.002',
            'taker_fee': '0.002',
            'trades_count': 0
        }
        return web.json_response(response, status=200)

    async def post_submit_cancel(self, _):
        response = {
            "status": "ok",
            "data": self.order_id
        }
        return web.json_response(response, status=200)

    async def get_order_update(self, _):
        response = self.order_response_dict[self.order_id]
        return web.json_response(response, status=200)

    async def post_batch_cancel(self, _):
        response = {
            "status": "ok",
            "data": {"success": self.cancel_all_order_ids, "failed": []}
        }
        return web.json_response(response, status=200)
