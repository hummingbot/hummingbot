class FixtureOKEx:

    TIMESTAMP = {'timestamp': 123}

    INSTRUMENT_TICKER = [{
        "best_ask": "7222.2",
        "best_bid": "7222.1",
        "instrument_id": "ETH-USDT",
        "product_id": "ETH-USDT",
        "last": "7222.2",
        "last_qty": "0.00136237",
        "ask": "7222.2",
        "best_ask_size": "0.09207739",
        "bid": "7222.1",
        "best_bid_size": "3.61314948",
        "open_24h": "7356.8",
        "high_24h": "7367.7",
        "low_24h": "7160",
        "base_volume_24h": "18577.2",
        "timestamp": "2019-12-11T07:48:04.014Z",
        "quote_volume_24h": "134899542.8"
    }]

    OKEX_INSTRUMENTS_URL = [{
        "base_currency": "ETH",
        "instrument_id": "ETH-USDT",
        "min_size": "0.001",
        "quote_currency": "USDT",
        "size_increment": "0.000001",
        "tick_size": "0.01"
    }]

    OKEX_ORDER_BOOK = {
        "asks": [
            [
                "406.63",
                "30",
                "1"
            ],
            [
                "406.64",
                "0.963",
                "1"
            ],
            [
                "406.65",
                "0.896838",
                "1"
            ],
            [
                "406.66",
                "1.989262",
                "2"
            ],
            [
                "406.67",
                "7.216546",
                "1"
            ],
            [
                "406.68",
                "3.049723",
                "2"
            ],
            [
                "406.69",
                "22.780498",
                "5"
            ],
            [
                "406.7",
                "10",
                "1"
            ],
            [
                "406.71",
                "2.012149",
                "1"
            ],

        ],
        "bids": [
            [
                "406.59",
                "5",
                "2"
            ],
            [
                "406.55",
                "47.280034",
                "10"
            ],
            [
                "406.54",
                "30.5",
                "2"
            ],
            [
                "406.51",
                "10.811852",
                "1"
            ],
            [
                "406.47",
                "31.001449",
                "2"
            ],
            [
                "406.46",
                "1",
                "1"
            ],
            [
                "406.43",
                "14.721",
                "2"
            ],
            [
                "406.42",
                "15.328",
                "2"
            ],
            [
                "406.4",
                "22.4",
                "3"
            ],
            [
                "406.38",
                "19",
                "4"
            ]
        ],
        "timestamp": "2020-08-19T17:11:30.711Z"
    }

    OKEX_BALANCE_URL = [
        {
            "frozen": "0",
            "hold": "0",
            "id": "",
            "currency": "USDT",
            "balance": "10000",
            "available": "9000",
            "holds": "0"
        },
        {
            "frozen": "0",
            "hold": "0",
            "id": "",
            "currency": "ETH",
            "balance": "5000",
            "available": "4000",
            "holds": "0"
        }
    ]

    ORDER_PLACE = {
        # "client_oid":"oktspot79",
        "error_message": "",
        "error_code": "0",
        "order_id": "2510789768709120",
        "result": True
    }

    ORDER_GET_LIMIT_BUY_UNFILLED = {
        "client_oid": "oktspot70",
        "created_at": "2019-03-15T02:52:56.000Z",
        "filled_notional": "3.8886",
        "filled_size": "0.001",
        "funds": "",
        "instrument_id": "ETH-USDT",
        "notional": "",
        "order_id": "2482659399697407",
        "order_type": "0",
        "price": "3927.3",
        "price_avg": "3927.3",
        "product_id": "ETH-USDT",
        "side": "buy",
        "size": "0.001",
        # status is soon to be deprecated
        # "status":"filled",
        "fee_currency": "BTC",
        "fee": "-0.01",
        "rebate_currency": "open",
        "rebate": "0.05",
        "state": "1",  # partially filled
        "timestamp": "2019-03-15T02:52:56.000Z",
        "type": "limit"
    }

    ORDER_GET_LIMIT_BUY_FILLED = {
        "client_oid": "oktspot70",
        "created_at": "2019-03-15T02:52:56.000Z",
        "filled_notional": "3.8886",
        "filled_size": "0.001",
        "funds": "",
        "instrument_id": "ETH-USDT",
        "notional": "",
        "order_id": "2482659399697408",
        "order_type": "0",
        "price": "3927.3",
        "price_avg": "3927.3",
        "product_id": "ETH-USDT",
        "side": "buy",
        "size": "0.001",
        # status is soon to be deprecated
        # "status":"",
        "fee_currency": "BTC",
        "fee": "-0.01",
        "rebate_currency": "open",
        "rebate": "0.05",
        "state": "2",  # filled
        "timestamp": "2019-03-15T02:52:56.000Z",
        "type": "limit"
    }

    ORDERS_BATCH_CANCELLED = {
        "ETH-USDT": [{
            "result": True,
            "error_message": "",
            "error_code": "0",
            "client_oid": "",
            "order_id": "2482659399697407"
        },
            {
            "result": True,
            "error_message": "",
            "error_code": "0",
            "client_oid": "",
            "order_id": "2482659399697408"
        }
        ]
    }

    ORDER_CANCEL = {
        "result": True,
        "client_oid": "a123",
        "order_id": "2510832677225473",
        "error_message": "",
        "error_code": "0"
    }

    ORDER_GET_CANCELED = {
        "client_oid": "oktspot70",
        "created_at": "2019-03-15T02:52:56.000Z",
        "filled_notional": "3.8886",
        "filled_size": "0.001",
        "funds": "",
        "instrument_id": "ETH-USDT",
        "notional": "",
        "order_id": "2482659399697407",
        "order_type": "0",
        "price": "3927.3",
        "price_avg": "3927.3",
        "product_id": "ETH-USDT",
        "side": "buy",
        "size": "0.001",
        # status is soon to be deprecated
        # "status":
        "fee_currency": "BTC",
        "fee": "-0.01",
        "rebate_currency": "open",
        "rebate": "0.05",
        "state": "-1",  # cancelled
        "timestamp": "2019-03-15T02:52:56.000Z",
        "type": "limit"
    }

    ORDER_GET_MARKET_BUY = {
        "client_oid": "oktspot12",
        "created_at": "2019-03-15T02:52:56.000Z",
        "filled_notional": "5.459999999999999816",
        "filled_size": "0.060015396458814472",
        "funds": "",
        "instrument_id": "ETH-USDT",
        "notional": "",
        "order_id": "2482659399697407",
        "order_type": "0",
        "price": "3927.3",
        "price_avg": "3927.3",
        "product_id": "ETH-USDT",
        "side": "buy",
        "size": "5.460000000000000000",
        # status is soon to be deprecated
        # "status":
        "fee_currency": "USDT",
        "fee": "000040030792917629",
        "rebate_currency": "open",
        "rebate": "0.05",
        "state": "2",  # partially filled
        "timestamp": "2019-03-15T02:52:56.000Z",
        "type": "market"
    }

    ORDER_GET_MARKET_SELL = {
        "client_oid": "oktspot12",
        "created_at": "2019-03-15T02:52:56.000Z",
        "filled_notional": "5.459999999999999816",
        "filled_size": "0.060000000000000000",
        "funds": "",
        "instrument_id": "ETH-USDT",
        "notional": "",
        "order_id": "2482659399697407",
        "order_type": "0",
        "price": "3927.3",
        "price_avg": "3927.3",
        "product_id": "ETH-USDT",
        "side": "sell",
        "size": "5.460000000000000000",
        # status is soon to be deprecated
        # "status":
        "fee_currency": "ETH",
        "fee": "000040030792917629",
        "rebate_currency": "open",
        "rebate": "0.05",
        "state": "2",  # fully filled
        "timestamp": "2019-03-15T02:52:56.000Z",
        "type": "market"
    }
