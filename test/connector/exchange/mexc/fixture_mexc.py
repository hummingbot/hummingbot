class FixtureMEXC:
    PING_DATA = {"code": 200}

    MEXC_TICKERS = {
        "code": "0",
        "msg": "",
        "data": [
            {
                "symbol": "ETH_USDT",
                "volume": "14155.61237",
                "high": "4394.18",
                "low": "4166.27",
                "bid": "4205.44",
                "ask": "4206.28",
                "open": "4311.7",
                "last": "4205.89",
                "time": 1635685800000,
                "change_rate": "-0.0245402"
            }
        ]
    }

    TICKER_DATA = {
        "code": 200,
        "data": [
            {
                "symbol": "ETH_USDT",
                "volume": "0",
                "high": "182.4117576",
                "low": "182.4117576",
                "bid": "182.0017985",
                "ask": "183.1983186",
                "open": "182.4117576",
                "last": "182.4117576",
                "time": 1574668200000,
                "change_rate": "0.00027307"
            }
        ]
    }

    MEXC_MARKET_SYMBOL = {
        "code": 200,
        "data": [
            {
                "symbol": "ETH_USDT",
                "state": "ENABLED",
                "vcoinName": "ETH",
                "vcoinStatus": 1,
                "price_scale": 2,
                "quantity_scale": 5,
                "min_amount": "5",
                "max_amount": "5000000",
                "maker_fee_rate": "0.002",
                "taker_fee_rate": "0.002",
                "limited": False,
                "etf_mark": 0,
                "symbol_partition": "MAIN"
            }
        ]
    }

    MEXC_ORDER_BOOK = {
        "code": 200,
        "data": {
            "asks": [
                {
                    "price": "183.1683154",
                    "quantity": "128.5"
                },
                {
                    "price": "183.1983186",
                    "quantity": "101.6"
                }
            ],
            "bids": [
                {
                    "price": "182.4417544",
                    "quantity": "115.5"
                },
                {
                    "price": "182.4217568",
                    "quantity": "135.7"
                }
            ]
        }
    }

    MEXC_BALANCE_URL = {
        "code": 200,
        "data": {
            "BTC": {
                "frozen": "0",
                "available": "140"
            },
            "ETH": {
                "frozen": "8471.296525048",
                "available": "483280.9653659222035"
            },
            "USDT": {
                "frozen": "0",
                "available": "27.3629"
            },
            "MX": {
                "frozen": "30.9863",
                "available": "450.0137"
            }
        }
    }

    ORDER_PLACE = {
        "code": 200,
        "data": "c8663a12a2fc457fbfdd55307b463495"
    }

    ORDER_GET_LIMIT_BUY_UNFILLED = {
        "code": 200,
        "data": [
            {
                "id": "2a0ad973f6a8452bae1533164ec3ef72",
                "symbol": "ETH_USDT",
                "price": "3500",
                "quantity": "0.06",
                "state": "NEW",
                "type": "BID",
                "deal_quantity": "0",
                "deal_amount": "0",
                "create_time": 1635824885000,
                "order_type": "LIMIT_ORDER"
            }
        ]
    }

    ORDER_GET_LIMIT_BUY_FILLED = {
        "code": 200,
        "data": [
            {
                "id": "c8663a12a2fc457fbfdd55307b463495",
                "symbol": "ETH_USDT",
                "price": "4001",
                "quantity": "0.06",
                "state": "FILLED",
                "type": "BID",
                "deal_quantity": "0.06",
                "deal_amount": "0.06",
                "create_time": 1573117266000,
                "client_order_id": "aaa"
            }
        ]
    }

    ORDERS_BATCH_CANCELLED = {
        "code": "0",
        "msg": "",
        "data": [
            {
                "clOrdId": "",
                "ordId": "2482659399697407",
                "sCode": "0",
                "sMsg": ""
            },
            {
                "clOrdId": "",
                "ordId": "2482659399697408",
                "sCode": "0",
                "sMsg": ""
            },
        ]
    }

    ORDER_CANCEL = {
        "code": 200,
        "data": {
            "2510832677225473": "success"
        }
    }

    ORDER_GET_CANCELED = {
        "code": 200,
        "data": [
            {
                "id": "c38a9449ee2e422ca83593833a2595d7",
                "symbol": "ETH_USDT",
                "price": "3500",
                "quantity": "0.06",
                "state": "CANCELED",
                "type": "BID",
                "deal_quantity": "0",
                "deal_amount": "0",
                "create_time": 1635822195000,
                "order_type": "LIMIT_ORDER"
            }
        ]
    }

    ORDER_GET_MARKET_BUY = {
        "code": 200,
        "data": [
            {
                "id": "c8663a12a2fc457fbfdd55307b463495",
                "symbol": "ETH_USDT",
                "price": "4001",
                "quantity": "0.06",
                "state": "FILLED",
                "type": "BID",
                "deal_quantity": "0.06",
                "deal_amount": "0.06",
                "create_time": 1573117266000,
                "client_order_id": "aaa"
            }
        ]
    }

    ORDER_GET_MARKET_SELL = {
        "code": 200,
        "data": [
            {
                "id": "c8663a12a2fc457fbfdd55307b463495",
                "symbol": "ETH_USDT",
                "price": "4001",
                "quantity": "0.06",
                "state": "FILLED",
                "type": "BID",
                "deal_quantity": "0.06",
                "deal_amount": "0.06",
                "create_time": 1573117266000,
                "client_order_id": "aaa"
            }
        ]
    }

    ORDER_DEAL_DETAIL = {
        "code": 200,
        "data": [
            {
                "symbol": "ETH_USDT",
                "order_id": "a39ea6b7afcf4f5cbba1e515210ff827",
                "quantity": "54.1",
                "price": "182.6317377",
                "amount": "9880.37700957",
                "fee": "9.88037700957",
                "trade_type": "BID",
                "fee_currency": "USDT",
                "is_taker": True,
                "create_time": 1572693911000
            }
        ]
    }
