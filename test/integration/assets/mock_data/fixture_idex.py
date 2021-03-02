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
