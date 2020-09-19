class FixtureDuedex:
    LIMIT_MAKER_ERROR = {"code": 10117, "message": "Post-only order rejected"}

    # General Exchange Info
    MARKETS = {"code": 0, "data": [
        {"instrumentId": "BTCUSD", "status": "open", "baseCurrencySymbol": "BTC", "quoteCurrencySymbol": "USD",
         "positionCurrency": {"symbol": "USD", "name": "US Dollar", "precision": 4},
         "settlementCurrency": {"symbol": "BTC", "name": "Bitcoin", "precision": 8},
         "expirationType": "perpetual", "markMethod": "fairPrice", "multiplier": "1", "quantoExchangeRate": "1",
         "isInverse": True, "isQuanto": False, "adlEnabled": True, "makerFee": "-0.000250", "takerFee": "0.000750",
         "lotSize": 1, "maxSize": 10000000, "pricePrecision": 2, "tickSize": "0.50", "maxPrice": "100000.00",
         "minInitMargin": "0.0100", "maintMargin": "0.0050", "baseRiskLimit": "100.00000000", "riskStep": "50.00000000",
         "maxRiskLimit": "600.00000000"},
        {"instrumentId": "BTCUSDT", "status": "open", "baseCurrencySymbol": "BTC", "quoteCurrencySymbol": "USDT",
         "positionCurrency": {"symbol": "BTC", "name": "Bitcoin", "precision": 8},
         "settlementCurrency": {"symbol": "USDT", "name": "Tether USD", "precision": 4},
         "expirationType": "perpetual", "markMethod": "fairPrice", "multiplier": "0.0001", "quantoExchangeRate": "1",
         "isInverse": False, "isQuanto": False, "adlEnabled": True, "makerFee": "-0.000250", "takerFee": "0.000750",
         "lotSize": 1, "maxSize": 10000000, "pricePrecision": 2, "tickSize": "0.50", "maxPrice": "100000.00",
         "minInitMargin": "0.0100", "maintMargin": "0.0050", "baseRiskLimit": "1000000.0000", "riskStep": "500000.0000",
         "maxRiskLimit": "6000000.0000"},
        {"instrumentId": "ETHUSDT", "status": "open", "baseCurrencySymbol": "ETH", "quoteCurrencySymbol": "USDT",
         "positionCurrency": {"symbol": "ETH", "name": "Ether", "precision": 6},
         "settlementCurrency": {"symbol": "USDT", "name": "Tether USD", "precision": 4},
         "expirationType": "perpetual", "markMethod": "fairPrice", "multiplier": "0.01", "quantoExchangeRate": "1",
         "isInverse": False, "isQuanto": False, "adlEnabled": True, "makerFee": "-0.000250", "takerFee": "0.000750",
         "lotSize": 1, "maxSize": 10000000, "pricePrecision": 2, "tickSize": "0.05", "maxPrice": "5000.00",
         "minInitMargin": "0.0200", "maintMargin": "0.0100", "baseRiskLimit": "1000000.0000", "riskStep": "500000.0000",
         "maxRiskLimit": "6000000.0000"},
        {"instrumentId": "LINKUSDT", "status": "open", "baseCurrencySymbol": "LINK", "quoteCurrencySymbol": "USDT",
         "positionCurrency": {"symbol": "LINK", "name": "ChainLink Token", "precision": 4},
         "settlementCurrency": {"symbol": "USDT", "name": "Tether USD", "precision": 4},
         "expirationType": "perpetual", "markMethod": "fairPrice", "multiplier": "0.1", "quantoExchangeRate": "1",
         "isInverse": False, "isQuanto": False, "adlEnabled": True, "makerFee": "0.000000", "takerFee": "0.000000",
         "lotSize": 1, "maxSize": 10000000, "pricePrecision": 3, "tickSize": "0.001", "maxPrice": "500.000",
         "minInitMargin": "0.0200", "maintMargin": "0.0100", "baseRiskLimit": "1000000.0000", "riskStep": "500000.0000",
         "maxRiskLimit": "6000000.0000"}]}

    TICKER = {"code": 0, "data": {"instrument": "BTCUSD", "bestBid": "10874.50", "bestAsk": "10875.00", "lastPrice": "10875.00", "indexPrice": "10871.89", "markPrice": "10872.21", "fundingRate": "0.000100", "nextFundingTime": "2020-09-17T12:00:00.000Z", "open": "10862.00", "high": "11098.00", "low": "10835.00", "close": "10875.00", "volume": 3608621, "openInterest": 849089}}

    # General User Info
    BALANCES = {'code': 0, 'data': [{'currency': 'BTC', 'available': '9.99999841', 'orderMargin': '0.00000000', 'positionMargin': '0.00000161', 'realisedPnl': '0.00000002', 'unrealisedPnl': '-0.00000062', 'bonusLeft': '0.00000000'}, {'currency': 'USDT', 'available': '100000.0000', 'orderMargin': '0.0000', 'positionMargin': '0.0000', 'realisedPnl': '0.0000', 'unrealisedPnl': '0.0000', 'bonusLeft': '0.0000'}]}

    ORDER_PLACE = {'code': 0, 'data': {'instrument': 'BTCUSD', 'orderId': 56, 'clientOrderId': 'buy-BTC-USD-1600334840999448', 'type': 'limit', 'isCloseOrder': False, 'side': 'long', 'price': '10494.00', 'size': 20, 'timeInForce': 'gtc', 'notionalValue': '0.00190585', 'status': 'new', 'fillPrice': '0.00', 'filledSize': 0, 'accumulatedFees': '0.00000000', 'createTime': '2020-09-17T09:27:20.858Z', 'updateTime': '2020-09-17T09:27:20.858Z'}}

    FILLED_BUY_LIMIT_ORDER = {'code': 0, 'data': {'instrument': 'BTCUSD', 'orderId': 69, 'clientOrderId': 'buy-BTC-USD-1600345272542904', 'type': 'limit', 'isCloseOrder': False, 'side': 'long', 'price': '11000.00', 'size': 10, 'timeInForce': 'gtc', 'notionalValue': '0.00090909', 'status': 'filled', 'fillPrice': '11000.00', 'filledSize': 10, 'accumulatedFees': '0.00000068', 'createTime': '2020-09-17T12:21:12.251Z', 'updateTime': '2020-09-17T12:21:12.251Z'}}

    FILLED_SELL_LIMIT_ORDER = {'code': 0, 'data': {'instrument': 'BTCUSD', 'orderId': 70, 'clientOrderId': 'sell-BTC-USD-1600345787542148', 'type': 'limit', 'isCloseOrder': False, 'side': 'short', 'price': '10000.00', 'size': 10, 'timeInForce': 'gtc', 'notionalValue': '0.00100000', 'status': 'filled', 'fillPrice': '10000.00', 'filledSize': 10, 'accumulatedFees': '0.00000075', 'createTime': '2020-09-17T12:29:47.160Z', 'updateTime': '2020-09-17T12:29:47.160Z'}}

    BUY_MARKET_ORDER = {'code': 0, 'data': {'instrument': 'BTCUSD', 'orderId': 71, 'clientOrderId': 'buy-BTC-USD-1600334840999449', 'type': 'market', 'isCloseOrder': False, 'side': 'long', 'size': 20, 'timeInForce': 'ioc', 'notionalValue': '0.00190585', 'status': 'new', 'fillPrice': '0.00', 'filledSize': 0, 'accumulatedFees': '0.00000000', 'createTime': '2020-09-17T09:27:20.858Z', 'updateTime': '2020-09-17T09:27:20.858Z'}}

    SELL_MARKET_ORDER = {'code': 0, 'data': {'instrument': 'BTCUSD', 'orderId': 72, 'clientOrderId': 'sell-BTC-USD-1600334840999450', 'type': 'market', 'isCloseOrder': False, 'side': 'long', 'size': 20, 'timeInForce': 'ioc', 'notionalValue': '0.00190585', 'status': 'new', 'fillPrice': '0.00', 'filledSize': 0, 'accumulatedFees': '0.00000000', 'createTime': '2020-09-17T09:27:20.858Z', 'updateTime': '2020-09-17T09:27:20.858Z'}}

    OPEN_BUY_LIMIT_ORDER = {'code': 0, 'data': {'instrument': 'BTCUSD', 'orderId': 56, 'clientOrderId': 'buy-BTC-USD-1600334840999451', 'type': 'limit', 'isCloseOrder': False, 'side': 'long', 'price': '10494.00', 'size': 20, 'timeInForce': 'gtc', 'notionalValue': '0.00190585', 'status': 'new', 'fillPrice': '0.00', 'filledSize': 0, 'accumulatedFees': '0.00000000', 'createTime': '2020-09-17T09:27:20.858Z', 'updateTime': '2020-09-17T09:27:20.858Z'}}

    OPEN_SELL_LIMIT_ORDER = {'code': 0, 'data': {'instrument': 'BTCUSD', 'orderId': 57, 'clientOrderId': 'sell-BTC-USD-1600334841000465', 'type': 'limit', 'isCloseOrder': False, 'side': 'short', 'price': '10706.00', 'size': 20, 'timeInForce': 'gtc', 'notionalValue': '0.00186811', 'status': 'new', 'fillPrice': '0.00', 'filledSize': 0, 'accumulatedFees': '0.00000000', 'createTime': '2020-09-17T09:27:20.858Z', 'updateTime': '2020-09-17T09:27:20.858Z'}}

    CANCEL_ORDER = {'code': 0}

    ORDERS_BATCH_CANCELLED = {'code': 0}
