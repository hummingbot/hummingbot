class FixtureIdex:
    # General Exchange Info
    MARKETS = None

    # General User Info
    BALANCES = None

    TRADE_FEES = None

    LISTEN_KEY = None

    # User Trade Info
    # Sample snapshot for trading pair ETH-USDC with sequence = 71228121

    SNAPSHOT_1 = {
        "sequence": 71228121,
        "bids": [
            ["202.00200000", "13.88204000", 2],
            ["202.00100000", "10.00000000", 3],
            ["198.02200000", "9.88204000", 2],
            ["196.10100000", "3.00000000", 9],

        ],
        "asks": [
            ["202.01000000", "4.11400000", 1],
            ["202.01200000", "7.50550000", 3],
            ["204.01000000", "8.11400000", 3],
            ["205.91200000", "12.60550000", 3],
            ["207.31000000", "8.11400000", 2],
            ["210.01200000", "13.50550000", 3],
        ]
    }

    # Sample snapshot for trading pair ETH-USDC with sequence = 71228122
    SNAPSHOT_2 = {
        "sequence": 71228122,
        "bids": [
            ["203.90200000", "9.88204000", 5],
            ["201.30100000", "6.00000000", 1],
            ["199.42200000", "7.88204000", 2],
            ["196.50100000", "2.00000000", 5],

        ],
        "asks": [
            ["204.11000000", "2.11400000", 1],
            ["205.01200000", "3.50550000", 7],
            ["206.01000000", "5.11400000", 5],
            ["208.91200000", "1.60550000", 2],
            ["210.31000000", "2.11400000", 1],
            ["211.01200000", "1.50550000", 3],
        ]
    }

    TRADING_PAIR_TRADES = [
        {
            "fillId": "3e3a7887-2c20-3705-95f4-8a64892612f3",
            "price": "0.00729011",
            "quantity": "200.00000000",
            "quoteQuantity": "1.45802200",
            "time": 1612385689385,
            "makerSide": "buy",
            "sequence": 7
        },
        {
            "fillId": "71ae1754-b92d-336c-9e82-15e1be7f3e01",
            "price": "0.01429000",
            "quantity": "37.21253813",
            "quoteQuantity": "0.53176716",
            "time": 1613839046778,
            "makerSide": "sell",
            "sequence": 8
        },
        {
            "fillId": "4b6a09ec-6fd5-3eb5-ba76-1ce2f1f85c4e",
            "price": "0.01780000",
            "quantity": "115.84889933",
            "quoteQuantity": "2.06211040",
            "time": 1614860652110,
            "makerSide": "sell",
            "sequence": 9
        }
    ]

    TRADING_PAIR_TICKER = {
        "market": "UNI-ETH",
        "time": 1614888274602,
        "open": "0.01780000",
        "high": "0.01780000",
        "low": "0.01780000",
        "close": "0.01780000",
        "closeQuantity": "115.84889933",
        "baseVolume": "115.84889933",
        "quoteVolume": "2.06211040",
        "percentChange": "0.00",
        "numTrades": 1,
        "ask": "0.02480000",
        "bid": "0.00755001",
        "sequence": 9
    }

    ORDER_BOOK_LEVEL2 = {
        "sequence": 39902171,
        "bids": [
            [
                "0.01850226",
                "172.86097063",
                1
            ],
            [
                "0.01850225",
                "540.47480710",
                1
            ]
        ],
        "asks": [
            [
                "0.02091798",
                "112.02217000",
                1
            ],
            [
                "0.02091799",
                "1607.13503722",
                2
            ]
        ]
    }

    BUY_MARKET_ORDER = None

    WS_AFTER_BUY_1 = None

    WS_AFTER_BUY_2 = None

    SELL_MARKET_ORDER = None

    WS_AFTER_SELL_1 = None

    WS_AFTER_SELL_2 = None

    BUY_LIMIT_ORDER = None

    SELL_LIMIT_ORDER = None

    LIMIT_MAKER_ERROR = None

    GET_DEPOSIT_INFO = None

    OPEN_BUY_ORDER = None

    OPEN_SELL_ORDER = None

    CANCEL_ORDER = None

    LINKETH_SNAP = None
    ZRXETH_SNAP = None

    ORDER_BUY_PRECISION = None

    ORDER_BUY_PRECISION_GET = None

    ORDER_SELL_PRECISION = None

    ORDER_SELL_PRECISION_GET = None
