from aiohttp import web


class HuobiMockAPI:
    MOCK_HUOBI_USER_ID = 10000000
    MOCK_HUOBI_LIMIT_BUY_ORDER_ID = 11111
    MOCK_HUOBI_LIMIT_SELL_ORDER_ID = 22222
    MOCK_HUOBI_MARKET_BUY_ORDER_ID = 33333
    MOCK_HUOBI_MARKET_SELL_ORDER_ID = 44444
    MOCK_HUOBI_LIMIT_CANCEL_ORDER_ID = 55555
    MOCK_HUOBI_LIMIT_OPEN_ORDER_ID = 66666
    MOCK_HUOBI_LIMIT_BUY_RESPONSE = {
        "status": "ok",
        "data": {
            "id": MOCK_HUOBI_LIMIT_BUY_ORDER_ID,
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
            "user-id": MOCK_HUOBI_USER_ID,
            "source": "spot-api",
            "state": "filled",
            "canceled-at": 0
        }
    }
    MOCK_HUOBI_LIMIT_SELL_RESPONSE = {
        "status": "ok",
        "data": {
            "id": MOCK_HUOBI_LIMIT_SELL_ORDER_ID,
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
            "user-id": MOCK_HUOBI_USER_ID,
            "source": "spot-api",
            "state": "filled",
            "canceled-at": 0
        }
    }
    MOCK_HUOBI_MARKET_BUY_RESPONSE = {
        "status": "ok",
        "data": {
            "id": MOCK_HUOBI_LIMIT_BUY_ORDER_ID,
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
    MOCK_HUOBI_MARKET_SELL_RESPONSE = {
        "status": "ok",
        "data": {
            "id": MOCK_HUOBI_MARKET_SELL_ORDER_ID,
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
            "user-id": MOCK_HUOBI_USER_ID,
            "source": "spot-api",
            "state": "filled",
            "canceled-at": 0
        }
    }
    MOCK_HUOBI_LIMIT_CANCEL_RESPONSE = {
        "status": "ok",
        "data": {
            "id": MOCK_HUOBI_LIMIT_CANCEL_ORDER_ID,
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
    MOCK_HUOBI_LIMIT_OPEN_RESPONSE = {
        "status": "ok",
        "data": {
            "id": MOCK_HUOBI_LIMIT_OPEN_ORDER_ID,
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
        self.cancel_all_order_ids = []
        self.order_response_dict = {
            self.MOCK_HUOBI_LIMIT_BUY_ORDER_ID: self.MOCK_HUOBI_LIMIT_BUY_RESPONSE,
            self.MOCK_HUOBI_LIMIT_SELL_ORDER_ID: self.MOCK_HUOBI_LIMIT_SELL_RESPONSE,
            self.MOCK_HUOBI_MARKET_BUY_ORDER_ID: self.MOCK_HUOBI_MARKET_BUY_RESPONSE,
            self.MOCK_HUOBI_MARKET_SELL_ORDER_ID: self.MOCK_HUOBI_MARKET_SELL_RESPONSE,
            self.MOCK_HUOBI_LIMIT_CANCEL_ORDER_ID: self.MOCK_HUOBI_LIMIT_CANCEL_RESPONSE,
            self.MOCK_HUOBI_LIMIT_OPEN_ORDER_ID: self.MOCK_HUOBI_LIMIT_OPEN_RESPONSE
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
            "status": "ok",
            "ts": 1570060262253,
            "data": [{
                "symbol": "ethusdt",
                "open": 175.57,
                "high": 181,
                "low": 175,
                "close": 180.11,
                "amount": 330265.5220692477,
                "vol": 58300213.797686026,
                "count": 93755
            }]
        }
        return web.json_response(response, status=200)

    async def get_account_accounts(self, _):
        response = {
            "status": "ok",
            "data": [{
                "id": self.MOCK_HUOBI_USER_ID,
                "type": "spot",
                "subtype": "",
                "state": "working"
            }]
        }
        return web.json_response(response, status=200)

    async def get_common_timestamp(self, _):
        response = {"status": "ok", "data": 1569445000000}
        return web.json_response(response, status=200)

    async def get_common_symbols(self, _):
        response = {
            "status": "ok",
            "data": [
                {
                    "base-currency": "eth",
                    "quote-currency": "usdt",
                    "price-precision": 2,
                    "amount-precision": 4,
                    "symbol-partition": "main",
                    "symbol": "ethusdt",
                    "state": "online",
                    "value-precision": 8,
                    "min-order-amt": 0.001,
                    "max-order-amt": 10000,
                    "min-order-value": 1
                }
            ]
        }
        return web.json_response(response, status=200)

    async def get_user_balance(self, _):
        response = {
            "status": "ok",
            "data": {
                "id": self.MOCK_HUOBI_USER_ID,
                "type": "spot",
                "state": "working",
                "list": [{
                    "currency": "eth",
                    "type": "trade",
                    "balance": "0.259942948171422263"
                }]
            }
        }
        return web.json_response(response, status=200)

    async def post_order_place(self, req: web.Request):
        response = {
            "status": "ok",
            "data": self.order_id
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
