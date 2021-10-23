class Fixturesouthxchange:
    TRADES = [
        {"At": 1633016333, "Amount": 0.99, "Price": 93.6, "Type": "buy"},
        {"At": 1633016259, "Amount": 1.0, "Price": 92.0, "Type": "sell"}
    ]

    FEES = {
        "Currencies": [
            {"Code": "BTC", "Name": "Bitcoin", "Precision": 8, "MinDeposit": 0.0, "DepositFeeMin": 0.0, "MinWithdraw": 0.1, "WithdrawFee": 0.001, "WithdrawFeeMin": 0.01},
            {"Code": "LTC2", "Name": "Litecoin2", "Precision": 8, "MinDeposit": 0.0, "DepositFeeMin": 0.0, "MinWithdraw": 0.1, "WithdrawFee": 0.001, "WithdrawFeeMin": 0.01},
            {"Code": "USD2", "Name": "US Dollar2", "Precision": 2, "MinDeposit": 0.0, "DepositFeeMin": 0.0, "MinWithdraw": 0.1, "WithdrawFee": 0.001, "WithdrawFeeMin": 0.01}
        ],
        "Markets": [
            {"ListingCurrencyCode": "LTC2", "ReferenceCurrencyCode": "BTC2", "MakerFee": 0.001, "TakerFee": 0.001, "MinOrderListingCurrency": None, "PricePrecision": None},
            {"ListingCurrencyCode": "LTC2", "ReferenceCurrencyCode": "USD2", "MakerFee": 0.001, "TakerFee": 0.001, "MinOrderListingCurrency": None, "PricePrecision": None}
        ],
        "TraderLevels": [
            {"Name": "prueba", "MinVolumeAmount": 0.001, "MinVolumeCurrency": "LTC2", "MakerFeeRebate": 0.01, "TakerFeeRebate": 0.0}
        ]
    }

    ORDERS_BOOK = {"BuyOrders": [{"Index": 0, "Amount": 0.011, "Price": 93.6}, {"Index": 1, "Amount": 1.0, "Price": 92.0}], "SellOrders": [{"Index": 0, "Amount": 0.99, "Price": 93.6}, {"Index": 1, "Amount": 9.9, "Price": 101.0}]}

    BALANCES = [
        {"Currency": "LTC2", "Deposited": 118.19343, "Available": 118.19343, "Unconfirmed": 0.0},
        {"Currency": "USD2", "Deposited": 873.28, "Available": 5873.28, "Unconfirmed": 0.0}
    ]

    MARKETS = [["BTC2", "USD2", 1], ["LTC2", "BTC2", 2], ["LTC2", "USD2", 3], ["ZEIT2", "LTC2", 4], ["BTC2", "USD4", 5]]

    ORDER_PLACE = "30001"

    GET_ORDER_RESPONSE_BUY_CREATE = {'Type': 'buy', 'Amount': 1.0, 'LimitPrice': 86.24, 'ListingCurrency': 'LTC2', 'ReferenceCurrency': 'USD2', 'Status': 'pending', 'DateAdded': '2021-10-02T14: 23: 17.2'}

    GET_ORDER_RESPONSE_BUY_EXECUTED = {"Type": "buy", "Amount": 1.0, "LimitPrice": 86.24, "ListingCurrency": "LTC2", "ReferenceCurrency": "USD2", "Status": "executed", "DateAdded": "2021-10-10T12: 32: 29.167"}

    GET_ORDER_RESPONSE_BUY_CANCEL = {"Type": "buy", "Amount": 1.0, "LimitPrice": 86.24, "ListingCurrency": "LTC2", "ReferenceCurrency": "USD2", "Status": "cancelednotexecuted", "DateAdded": "2021-10-10T12: 32: 29.167"}

    GET_ORDER_RESPONSE_SELL_CREATE = {'Type': 'sell', 'Amount': 1.0, 'LimitPrice': 102.96, 'ListingCurrency': 'LTC2', 'ReferenceCurrency': 'USD2', 'Status': 'pending', 'DateAdded': '2021-10-02T14: 23: 17.2'}

    GET_ORDER_RESPONSE_SELL_EXECUTED = {"Type": "sell", "Amount": 1.0, "LimitPrice": 86.24, "ListingCurrency": "LTC2", "ReferenceCurrency": "USD2", "Status": "executed", "DateAdded": "2021-10-10T12: 32: 29.167"}

    GET_ORDER_RESPONSE_SELL_CANCEL = {"Type": "sell", "Amount": 1.0, "LimitPrice": 86.24, "ListingCurrency": "LTC2", "ReferenceCurrency": "USD2", "Status": "cancelednotexecuted", "DateAdded": "2021-10-10T12: 32: 29.167"}

    OPEN_ORDERS_BUY = {"Type": "buy", "Amount": 1.0, "OriginalAmount": 1.0, "LimitPrice": 84.24, "ListingCurrency": "LTC2", "ReferenceCurrency": "USD2"}

    OPEN_ORDERS_SELL = {"Type": "sell", "Amount": 1.0, "OriginalAmount": 1.0, "LimitPrice": 102.96, "ListingCurrency": "LTC2", "ReferenceCurrency": "USD2"}

    OPEN_ORDERS = []

    WS_AFTER_BUY = {
        "k": "order",
        "v": [
            {"m": 0, "d": "0001-01-01T00: 00: 00", "get": None, "giv": None, "a": 0.0, "oa": 0.0, "p": 0.0, "b": True}
        ]
    }

    WS_AFTER_CANCEL_BUY = {
        "k": "order",
        "v": [
            {"m": 0, "d": "0001-01-01T00: 00: 00", "get": None, "giv": None, "a": 0.0, "oa": 0.0, "p": 0.0, "b": True}
        ]
    }

    WS_AFTER_SELL = {
        "k": "order",
        "v": [
            {"m": 0, "d": "0001-01-01T00: 00: 00", "get": None, "giv": None, "a": 0.0, "oa": 0.0, "p": 0.0, "b": False}
        ]
    }

    WS_AFTER_CANCEL_SELL = {
        "k": "order",
        "v": [
            {"m": 0, "d": "0001-01-01T00: 00: 00", "get": None, "giv": None, "a": 0.0, "oa": 0.0, "p": 0.0, "b": False}
        ]
    }

    LIST_TRANSACTIONS_ = {
        "TotalElements": 6,
        "Result": [
            {"Date": "2021-10-10T12: 53: 00.5", "CurrencyCode": "LTC2", "Amount": 0.5, "TotalBalance": 84.24000, "Type": "trade", "Status": "confirmed", "Address": None, "Hash": None, "Price": 86.24, "OtherAmount": 43.12, "OtherCurrency": "USD2", "OrderCode": "20001", "TradeId": 110010, "MovementId": None},
            {"Date": "2021-10-10T12: 53: 00.5", "CurrencyCode": "LTC2", "Amount": -0.0005, "TotalBalance": 119.17044, "Type": "tradefee", "Status": "confirmed", "Address": None, "Hash": None, "Price": 0.0, "OtherAmount": 0.0, "OtherCurrency": None, "OrderCode": None, "TradeId": 110010, "MovementId": None},
            {"Date": "2021-10-10T12: 53: 00.497", "CurrencyCode": "USD2", "Amount": -43.12, "TotalBalance": 5787.31, "Type": "trade", "Status": "confirmed", "Address": None, "Hash": None, "Price": 86.24, "OtherAmount": 0.5, "OtherCurrency": "LTC2", "OrderCode": "20001", "TradeId": 110010, "MovementId": None},
            {"Date": "2021-10-10T12: 51: 43.87", "CurrencyCode": "LTC2", "Amount": -0.0005, "TotalBalance": 118.67094, "Type": "tradefee", "Status": "confirmed", "Address": None, "Hash": None, "Price": 0.0, "OtherAmount": 0.0, "OtherCurrency": None, "OrderCode": None, "TradeId": 110009, "MovementId": None},
            {"Date": "2021-10-10T12: 51: 43.867", "CurrencyCode": "LTC2", "Amount": 0.5, "TotalBalance": 118.67144, "Type": "trade", "Status": "confirmed", "Address": None, "Hash": None, "Price": 86.24, "OtherAmount": 43.12, "OtherCurrency": "USD2", "OrderCode": "20001", "TradeId": 110009, "MovementId": None},
            {"Date": "2021-10-10T12: 51: 43.863", "CurrencyCode": "USD2", "Amount": -43.12, "TotalBalance": 5830.43, "Type": "trade", "Status": "confirmed", "Address": None, "Hash": None, "Price": 86.24, "OtherAmount": 0.5, "OtherCurrency": "LTC2", "OrderCode": "20001", "TradeId": 110009, "MovementId": None}
        ]
    }

    LIST_TRANSACTIONS = {
        "TotalElements": 9,
        "Result": [
            {"Date": "2021-10-11T15: 47: 05.883", "CurrencyCode": "LTC2", "Amount": 0.4, "TotalBalance": 120.16984, "Type": "trade", "Status": "confirmed", "Address": None, "Hash": None, "Price": 86.24, "OtherAmount": 34.49, "OtherCurrency": "USD2", "OrderCode": "250048", "TradeId": 110013, "MovementId": None},
            {"Date": "2021-10-11T15: 47: 05.883", "CurrencyCode": "LTC2", "Amount": -0.0004, "TotalBalance": 120.16944, "Type": "tradefee", "Status": "confirmed", "Address": None, "Hash": None, "Price": 0.0, "OtherAmount": 0.0, "OtherCurrency": None, "OrderCode": None, "TradeId": 110013, "MovementId": None},
            {"Date": "2021-10-11T15: 47: 05.877", "CurrencyCode": "USD2", "Amount": -34.49, "TotalBalance": 5701.08, "Type": "trade", "Status": "confirmed", "Address": None, "Hash": None, "Price": 86.24, "OtherAmount": 0.4, "OtherCurrency": "LTC2", "OrderCode": "250048", "TradeId": 110013, "MovementId": None},
            {"Date": "2021-10-11T15: 46: 59.02", "CurrencyCode": "LTC2", "Amount": 0.3, "TotalBalance": 119.77014, "Type": "trade", "Status": "confirmed", "Address": None, "Hash": None, "Price": 86.24, "OtherAmount": 25.87, "OtherCurrency": "USD2", "OrderCode": "250048", "TradeId": 110012, "MovementId": None},
            {"Date": "2021-10-11T15: 46: 59.02", "CurrencyCode": "LTC2", "Amount": -0.0003, "TotalBalance": 119.76984, "Type": "tradefee", "Status": "confirmed", "Address": None, "Hash": None, "Price": 0.0, "OtherAmount": 0.0, "OtherCurrency": None, "OrderCode": None, "TradeId": 110012, "MovementId": None},
            {"Date": "2021-10-11T15: 46: 59.017", "CurrencyCode": "USD2", "Amount": -25.87, "TotalBalance": 5735.57, "Type": "trade", "Status": "confirmed", "Address": None, "Hash": None, "Price": 86.24, "OtherAmount": 0.3, "OtherCurrency": "LTC2", "OrderCode": "250048", "TradeId": 110012, "MovementId": None},
            {"Date": "2021-10-11T15: 46: 50.4", "CurrencyCode": "LTC2", "Amount": 0.3, "TotalBalance": 119.47044, "Type": "trade", "Status": "confirmed", "Address": None, "Hash": None, "Price": 86.24, "OtherAmount": 25.87, "OtherCurrency": "USD2", "OrderCode": "250048", "TradeId": 110011, "MovementId": None},
            {"Date": "2021-10-11T15: 46: 50.4", "CurrencyCode": "LTC2", "Amount": -0.0003, "TotalBalance": 119.47014, "Type": "tradefee", "Status": "confirmed", "Address": None, "Hash": None, "Price": 0.0, "OtherAmount": 0.0, "OtherCurrency": None, "OrderCode": None, "TradeId": 110011, "MovementId": None},
            {"Date": "2021-10-11T15: 46: 50.393", "CurrencyCode": "USD2", "Amount": -25.87, "TotalBalance": 5761.44, "Type": "trade", "Status": "confirmed", "Address": None, "Hash": None, "Price": 86.24, "OtherAmount": 0.3, "OtherCurrency": "LTC2", "OrderCode": "250048", "TradeId": 110011, "MovementId": None}
        ]
    }
