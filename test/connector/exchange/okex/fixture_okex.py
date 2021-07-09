class FixtureOKEx:

    TIMESTAMP = {"code": "0", "msg": "", "data": [{"ts": "123"}]}

    OKEX_TICKERS = {
        "code": "0",
        "msg": "",
        "data": [
            {
                "instType": "SPOT",
                "instId": "ETH-USDT",
                "last": "9999.99",
                "lastSz": "0.1",
                "askPx": "9999.99",
                "askSz": "11",
                "bidPx": "8888.88",
                "bidSz": "5",
                "open24h": "9000",
                "high24h": "10000",
                "low24h": "8888.88",
                "volCcy24h": "2222",
                "vol24h": "2222",
                "sodUtc0": "2222",
                "sodUtc8": "2222",
                "ts": "1597026383085"
            },
        ]
    }

    INSTRUMENT_TICKER = [
        {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instType": "SPOT",
                    "instId": "ETH-USDT",
                    "uly": "ETH-USDT",
                    "category": "1",
                    "baseCcy": "ETH",
                    "quoteCcy": "USDT",
                    "settleCcy": "",
                    "ctVal": "",
                    "ctMult": "",
                    "ctValCcy": "",
                    "optType": "",
                    "stk": "",
                    "listTime": "1597026383085",
                    "expTime": "",
                    "lever": "",
                    "tickSz": "0.01",
                    "lotSz": "1",
                    "minSz": "1",
                    "ctType": "",
                    "alias": "",
                    "state": "live"
                }
            ]
        }
    ]

    OKEX_INSTRUMENTS_URL = {
        "code": "0",
        "msg": "",
        "data": [
            {
                "instType": "SPOT",
                "instId": "ETH-USDT",
                "uly": "ETH-USDT",
                "category": "1",
                "baseCcy": "ETH",
                "quoteCcy": "USDT",
                "settleCcy": "",
                "ctVal": "",
                "ctMult": "",
                "ctValCcy": "",
                "optType": "",
                "stk": "",
                "listTime": "",
                "expTime": "",
                "lever": "",
                "tickSz": "0.01",
                "lotSz": "0.000001",
                "minSz": "0.001",
                "ctType": "",
                "alias": "",
                "state": "live"
            }
        ]
    }

    OKEX_ORDER_BOOK = {
        "code": "0",
        "msg": "",
        "data": [
            {
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
                "ts": "1597026383085"
            }
        ]
    }

    OKEX_BALANCE_URL = {
        "code": "0",
        "msg": "",
        "data": [{
            "uTime": "",
            "totalEq": "",
            "adjEq": "91884.8502560037982063",
            "isoEq": "0",
            "ordFroz": "0",
            "imr": "0",
            "mmr": "0",
            "mgnRatio": "",
            "details": [
                {
                    "availBal": "4000",
                    "availEq": "1",
                    "ccy": "ETH",
                    "cashBal": "5000",
                    "disEq": "",
                    "eq": "",
                    "frozenBal": "0",
                    "interest": "0",
                    "isoEq": "0",
                    "liab": "0",
                    "mgnRatio": "",
                    "ordFrozen": "0",
                    "upl": "0",
                    "uplLiab": "0",
                    "crossLiab": "0",
                    "isoLiab": "0",
                    "uTIme": ""
                },
                {
                    "availBal": "9000",
                    "availEq": "1",
                    "ccy": "USDT",
                    "cashBal": "10000",
                    "disEq": "",
                    "eq": "",
                    "frozenBal": "0",
                    "interest": "0",
                    "isoEq": "0",
                    "liab": "0",
                    "mgnRatio": "",
                    "ordFrozen": "0",
                    "upl": "0",
                    "uplLiab": "0",
                    "crossLiab": "0",
                    "isoLiab": "0",
                    "uTIme": ""
                }
            ]
        }
        ]
    }

    ORDER_PLACE = {
        "code": "0",
        "msg": "",
        "data": [
            {
                "clOrdId": "oktspot79",
                "ordId": "2510789768709120",
                "tag": "",
                "sCode": "0",
                "sMsg": ""
            }
        ]
    }

    ORDER_GET_LIMIT_BUY_UNFILLED = {
        "arg": {
            "channel": "orders",
            "instType": "SPOT",
            "instId": "ETH-USDT"
        },
        "data": [
            {
                "instType": "SPOT",
                "instId": "ETH-USDT",
                "ccy": "ETH",
                "ordId": "2482659399697407",
                "clOrdId": "oktspot70",
                "tag": "",
                "px": "3927.3",
                "sz": "0.001",
                "ordType": "limit",
                "side": "buy",
                "posSide": "",
                "tdMode": "",
                "fillSz": "0",
                "fillPx": "long",
                "tradeId": "0",
                "accFillSz": "323",
                "fillTime": "0",
                "fillFee": "0.0001",
                "fillFeeCcy": "USDT",
                "execType": "M",
                "state": "partially_filled",
                "avgPx": "3927.3",
                "lever": "",
                "tpTriggerPx": "0",
                "tpOrdPx": "",
                "slTriggerPx": "0",
                "slOrdPx": "",
                "feeCcy": "",
                "fee": "0.01",
                "rebateCcy": "",
                "rebate": "",
                "pnl": "",
                "category": "",
                "uTime": "1597026383085",
                "cTime": "1597026383085",
                "reqId": "",
                "amendResult": "",
                "code": "0",
                "msg": ""
            }
        ]
    }

    ORDER_GET_LIMIT_BUY_FILLED = {
        "arg": {
            "channel": "orders",
            "instType": "SPOT",
            "instId": "ETH-USDT"
        },
        "data": [
            {
                "instType": "SPOT",
                "instId": "ETH-USDT",
                "ccy": "ETH",
                "ordId": "2482659399697408",
                "clOrdId": "oktspot70",
                "tag": "",
                "px": "3927.3",
                "sz": "0.001",
                "ordType": "limit",
                "side": "buy",
                "posSide": "",
                "tdMode": "",
                "fillSz": "0.001",
                "fillPx": "long",
                "tradeId": "0",
                "accFillSz": "323",
                "fillTime": "0",
                "fillFee": "0.0001",
                "fillFeeCcy": "USDT",
                "execType": "M",
                "state": "filled",
                "avgPx": "3927.3",
                "lever": "",
                "tpTriggerPx": "0",
                "tpOrdPx": "",
                "slTriggerPx": "0",
                "slOrdPx": "",
                "feeCcy": "",
                "fee": "-0.01",
                "rebateCcy": "",
                "rebate": "",
                "pnl": "",
                "category": "",
                "uTime": "1597026383085",
                "cTime": "1597026383085",
                "reqId": "",
                "amendResult": "",
                "code": "0",
                "msg": ""
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
        "code": "0",
        "msg": "",
        "data": [
            {
                "clOrdId": "a123",
                "ordId": "2510832677225473",
                "sCode": "0",
                "sMsg": ""
            }
        ]
    }

    ORDER_GET_CANCELED = {
        "code": "0",
        "msg": "",
        "data": [
            {
                "instType": "SPOT",
                "instId": "ETH-USDT",
                "ccy": "ETH",
                "ordId": "2482659399697407",
                "clOrdId": "oktspot70",
                "tag": "",
                "px": "3927.3",
                "sz": "0.001",
                "ordType": "limit",
                "side": "buy",
                "posSide": "",
                "tdMode": "",
                "fillSz": "0",
                "fillPx": "long",
                "tradeId": "0",
                "accFillSz": "323",
                "fillTime": "0",
                "fillFee": "0.0001",
                "fillFeeCcy": "USDT",
                "execType": "M",
                "state": "canceled",
                "avgPx": "3927.3",
                "lever": "",
                "tpTriggerPx": "0",
                "tpOrdPx": "",
                "slTriggerPx": "0",
                "slOrdPx": "",
                "feeCcy": "",
                "fee": "-0.01",
                "rebateCcy": "",
                "rebate": "",
                "pnl": "",
                "category": "",
                "uTime": "1597026383085",
                "cTime": "1597026383085",
                "reqId": "",
                "amendResult": "",
                "code": "0",
                "msg": ""
            }
        ]
    }

    ORDER_GET_MARKET_BUY = {
        "arg": {
            "channel": "orders",
            "instType": "SPOT",
            "instId": "ETH-USDT"
        },
        "data": [
            {
                "instType": "SPOT",
                "instId": "ETH-USDT",
                "ccy": "ETH",
                "ordId": "2482659399697407",
                "clOrdId": "oktspot12",
                "tag": "",
                "px": "3927.3",
                "sz": "0.060015396458814472",
                "ordType": "limit",
                "side": "buy",
                "posSide": "",
                "tdMode": "",
                "fillSz": "0.060015396458814472",
                "fillPx": "long",
                "tradeId": "0",
                "accFillSz": "0.060015396458814472",
                "fillTime": "0",
                "fillFee": "0.0001",
                "fillFeeCcy": "USDT",
                "execType": "T",
                "state": "filled",
                "avgPx": "3927.3",
                "lever": "",
                "tpTriggerPx": "0",
                "tpOrdPx": "",
                "slTriggerPx": "0",
                "slOrdPx": "",
                "feeCcy": "",
                "fee": "0.01",
                "rebateCcy": "",
                "rebate": "",
                "pnl": "",
                "category": "",
                "uTime": "1597026383085",
                "cTime": "1597026383085",
                "reqId": "",
                "amendResult": "",
                "code": "0",
                "msg": ""
            }
        ]
    }

    ORDER_GET_MARKET_SELL = {
        "arg": {
            "channel": "orders",
            "instType": "SPOT",
            "instId": "ETH-USDT"
        },
        "data": [
            {
                "instType": "SPOT",
                "instId": "ETH-USDT",
                "ccy": "ETH",
                "ordId": "2482659399697407",
                "clOrdId": "oktspot12",
                "tag": "",
                "px": "3927.3",
                "sz": "0.060015396458814472",
                "ordType": "limit",
                "side": "buy",
                "posSide": "",
                "tdMode": "",
                "fillSz": "0.060000",
                "fillPx": "long",
                "tradeId": "0",
                "accFillSz": "0.060000",
                "fillTime": "0",
                "fillFee": "0.0001",
                "fillFeeCcy": "USDT",
                "execType": "T",
                "state": "filled",
                "avgPx": "3927.3",
                "lever": "",
                "tpTriggerPx": "0",
                "tpOrdPx": "",
                "slTriggerPx": "0",
                "slOrdPx": "",
                "feeCcy": "",
                "fee": "0.01",
                "rebateCcy": "",
                "rebate": "",
                "pnl": "",
                "category": "",
                "uTime": "1597026383085",
                "cTime": "1597026383085",
                "reqId": "",
                "amendResult": "",
                "code": "0",
                "msg": ""
            }
        ]
    }
