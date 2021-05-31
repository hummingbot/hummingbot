class FixtureKucoin:
    BALANCES = {"code": "200000", "data": [
        {"balance": "0.1910973", "available": "0.1910973", "holds": "0", "currency": "ETH",
         "id": "5e3291017e612d0009cb8fa6", "type": "trade"},
        {"balance": "1", "available": "1", "holds": "0", "currency": "GRIN", "id": "5e32910f6743620009c134b0",
         "type": "trade"},
        {"balance": "0", "available": "0", "holds": "0", "currency": "ETH", "id": "5e3275507cb36900083d9f8e",
         "type": "main"}]}

    ORDER_PLACE = {"code": "200000", "data": {"orderId": "5e3cd0540fb53d000961491a"}}

    FILLED_SELL_LIMIT_ORDER = {
        "code": "200000",
        "data": {
            "symbol": "ETH-USDT", "hidden": False, "opType": "DEAL", "fee": "0.0021957",
            "channel": "API", "feeCurrency": "USDT", "type": "limit", "isActive": False,
            "createdAt": 1581043796000, "visibleSize": "0", "price": "208.61",
            "iceberg": False, "stopTriggered": False, "funds": "0",
            "id": "5e3cd0540fb53d000961491a", "timeInForce": "GTC", "tradeType": "TRADE",
            "side": "sell", "dealSize": "0.01", "cancelAfter": 0, "dealFunds": "2.1957",
            "stp": "", "postOnly": False, "stopPrice": "0", "size": "0.01", "stop": "",
            "cancelExist": False, "clientOid": "sell-ETH-USDT-1581043796007943"}}

    FILLED_BUY_LIMIT_ORDER = {
        "code": "200000",
        "data": {
            "symbol": "ETH-USDT", "hidden": False, "opType": "DEAL", "fee": "0.001969718114",
            "channel": "API", "feeCurrency": "USDT", "type": "limit", "isActive": False,
            "createdAt": 1581045461000, "visibleSize": "0", "price": "229.8", "iceberg": False,
            "stopTriggered": False, "funds": "0", "id": "5e3cd6d56e350a00094d32b8",
            "timeInForce": "GTC", "tradeType": "TRADE", "side": "buy", "dealSize": "0.01",
            "cancelAfter": 0, "dealFunds": "1.969718114", "stp": "", "postOnly": False,
            "stopPrice": "0", "size": "0.01", "stop": "", "cancelExist": False,
            "clientOid": "buy-ETH-USDT-1581045461006371"}}

    SELL_MARKET_ORDER = {
        "code": "200000",
        "data": {
            "symbol": "ETH-USDT", "hidden": False, "opType": "DEAL", "fee": "0.002401058172",
            "channel": "API", "feeCurrency": "USDT", "type": "market", "isActive": False,
            "createdAt": 1581055817000, "visibleSize": "0", "price": "0", "iceberg": False,
            "stopTriggered": False, "funds": "0", "id": "5e3cff496e350a0009aa51d6",
            "timeInForce": "GTC", "tradeType": "TRADE", "side": "sell",
            "dealSize": "0.0109999", "cancelAfter": 0, "dealFunds": "2.401058172", "stp": "",
            "postOnly": False, "stopPrice": "0", "size": "0.0109999", "stop": "",
            "cancelExist": False, "clientOid": "sell-ETH-USDT-1581055817012353"}}

    BUY_MARKET_ORDER = {
        "code": "200000",
        "data": {
            "symbol": "ETH-USDT", "hidden": False, "opType": "DEAL", "fee": "0.0021843",
            "channel": "API", "feeCurrency": "USDT", "type": "market", "isActive": False,
            "createdAt": 1581056207000, "visibleSize": "0", "price": "0", "iceberg": False,
            "stopTriggered": False, "funds": "0", "id": "5e3d00cf1fbc8d0008d81a18",
            "timeInForce": "GTC", "tradeType": "TRADE", "side": "buy", "dealSize": "0.01",
            "cancelAfter": 0, "dealFunds": "2.1843", "stp": "", "postOnly": False,
            "stopPrice": "0", "size": "0.01", "stop": "", "cancelExist": False,
            "clientOid": "buy-ETH-USDT-1581056207008008"}}

    CANCEL_ORDER = {"code": "200000", "data": {"cancelledOrderIds": ["5e3d03c86e350a0009b380a7"]}}

    OPEN_SELL_LIMIT_ORDER = {
        "code": "200000",
        "data": {
            "symbol": "ETH-USDT", "hidden": False, "opType": "DEAL", "fee": "0",
            "channel": "API",
            "feeCurrency": "USDT", "type": "limit", "isActive": True,
            "createdAt": 1581056968000,
            "visibleSize": "0", "price": "240.11", "iceberg": False,
            "stopTriggered": False,
            "funds": "0", "id": "5e3d03c86e350a0009b380a7", "timeInForce": "GTC",
            "tradeType": "TRADE", "side": "sell", "dealSize": "0", "cancelAfter": 0,
            "dealFunds": "0", "stp": "", "postOnly": False, "stopPrice": "0",
            "size": "0.01",
            "stop": "", "cancelExist": False,
            "clientOid": "sell-ETH-USDT-1581056966892386"}}

    GET_CANCELLED_ORDER = {
        "code": "200000",
        "data": {
            "symbol": "ETH-USDT", "hidden": False, "opType": "DEAL", "fee": "0",
            "channel": "API", "feeCurrency": "USDT", "type": "limit", "isActive": False,
            "createdAt": 1581056968000, "visibleSize": "0", "price": "240.11", "iceberg": False,
            "stopTriggered": False, "funds": "0", "id": "5e3d03c86e350a0009b380a7",
            "timeInForce": "GTC", "tradeType": "TRADE", "side": "sell", "dealSize": "0",
            "cancelAfter": 0, "dealFunds": "0", "stp": "", "postOnly": False, "stopPrice": "0",
            "size": "0.01", "stop": "", "cancelExist": True,
            "clientOid": "sell-ETH-USDT-1581056966892386"}}

    ORDER_PLACE_2 = {"code": "200000", "data": {"orderId": "5e3d08516e350a0009bcd272"}}

    OPEN_BUY_LIMIT_ORDER = {
        "code": "200000",
        "data": {
            "symbol": "ETH-USDT", "hidden": False, "opType": "DEAL", "fee": "0",
            "channel": "API", "feeCurrency": "USDT", "type": "limit", "isActive": True,
            "createdAt": 1581058129000, "visibleSize": "0", "price": "174.61",
            "iceberg": False, "stopTriggered": False, "funds": "0",
            "id": "5e3d08516e350a0009bcd272", "timeInForce": "GTC", "tradeType": "TRADE",
            "side": "buy", "dealSize": "0", "cancelAfter": 0, "dealFunds": "0", "stp": "",
            "postOnly": False, "stopPrice": "0", "size": "0.01", "stop": "",
            "cancelExist": False, "clientOid": "buy-ETH-USDT-1581058129011078"}}

    ORDERS_BATCH_CANCELLED = {
        "code": "200000",
        "data": {"cancelledOrderIds": ["5e3d0851051a350008723a81", "5e3d08516e350a0009bcd272"]}}
