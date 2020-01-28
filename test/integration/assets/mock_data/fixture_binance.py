class FixtureBinance:
    GET_ACCOUNT = {"makerCommission": 10, "takerCommission": 10, "buyerCommission": 0, "sellerCommission": 0,
                   "canTrade": True, "canWithdraw": True, "canDeposit": True, "updateTime": 1580009996654,
                   "accountType": "SPOT", "balances": [{"asset": "BTC", "free": "0.00000000", "locked": "0.00000000"},
                                                       {"asset": "ETH", "free": "0.77377698", "locked": "0.00000000"},
                                                       {"asset": "LINK", "free": "1.99700000", "locked": "0.00000000"}]}

    GET_TRADE_FEES = {"tradeFee": [{"symbol": "LINKBTC", "maker": 0.0010, "taker": 0.0010},
                                   {"symbol": "LINKBUSD", "maker": 0.0000, "taker": 0.0010},
                                   {"symbol": "LINKETH", "maker": 0.0010, "taker": 0.0010},
                                   {"symbol": "ZRXUSDT", "maker": 0.0010, "taker": 0.0010}], "success": True}

    GET_LISTEN_KEY = {'listenKey': 'lbGBXAh56py6THGEWu84Ma0zikdtzGfwXVujN6sL6q16KKvAOo4eJuftICxX'}

    POST_ORDER_BUY = {"symbol": "LINKETH", "orderId": 153849723, "orderListId": -1,
                      "clientOrderId": "buy-LINKETH-1580093594011279", "transactTime": 1580093594072,
                      "price": "0.00000000", "origQty": "1.00000000", "executedQty": "1.00000000",
                      "cummulativeQuoteQty": "0.01553045", "status": "FILLED", "timeInForce": "GTC", "type": "MARKET",
                      "side": "BUY", "fills": [{"price": "0.01553045", "qty": "1.00000000", "commission": "0.00100000",
                                                "commissionAsset": "LINK", "tradeId": 6034666}]}

    WS_AFTER_BUY_1 = {"e": "executionReport", "E": 1580204166110, "s": "LINKETH", "c": "buy-LINKETH-1580204166011219",
                      "S": "BUY",
                      "o": "MARKET", "f": "GTC", "q": "1.00000000", "p": "0.00000000", "P": "0.00000000",
                      "F": "0.00000000",
                      "g": -1, "C": "", "x": "NEW", "X": "NEW", "r": "NONE", "i": 154152657, "l": "0.00000000",
                      "z": "0.00000000",
                      "L": "0.00000000", "n": "0", "N": None, "T": 1580204166108, "t": -1, "I": 314324691, "w": True,
                      "m": False,
                      "M": False, "O": 1580204166108, "Z": "0.00000000", "Y": "0.00000000", "Q": "0.00000000"}

    WS_AFTER_BUY_2 = {"e": "executionReport", "E": 1580204166110, "s": "LINKETH", "c": "buy-LINKETH-1580204166011219",
                      "S": "BUY", "o": "MARKET", "f": "GTC", "q": "1.00000000", "p": "0.00000000", "P": "0.00000000",
                      "F": "0.00000000", "g": -1, "C": "", "x": "TRADE", "X": "FILLED", "r": "NONE", "i": 154152657,
                      "l": "1.00000000", "z": "1.00000000", "L": "0.01525328", "n": "0.00100000", "N": "LINK",
                      "T": 1580204166108, "t": 6040818, "I": 314324692, "w": False, "m": False, "M": True,
                      "O": 1580204166108, "Z": "0.01525328", "Y": "0.01525328", "Q": "0.00000000"}

    WS_AFTER_BUY_3 = {"e": "outboundAccountInfo", "E": 1580194595188, "m": 10, "t": 10, "b": 0, "s": 0, "T": True,
                      "W": True, "D": True, "u": 1580194595186,
                      "B": [{"a": "ETH", "f": "0.72699811", "l": "0.00000000"},
                            {"a": "LINK", "f": "4.98900000", "l": "0.00000000"}]}

    ORDER_GET_AFTER_BUY = {"symbol": "LINKETH", "orderId": 153849723, "orderListId": -1,
                           "clientOrderId": "buy-LINKETH-1580093594011279", "price": "0.00000000",
                           "origQty": "1.00000000", "executedQty": "1.00000000", "cummulativeQuoteQty": "0.01553045",
                           "status": "FILLED", "timeInForce": "GTC", "type": "MARKET", "side": "BUY",
                           "stopPrice": "0.00000000", "icebergQty": "0.00000000", "time": 1580093594072,
                           "updateTime": 1580093594072, "isWorking": True, "origQuoteOrderQty": "0.00000000"}

    POST_ORDER_SELL = {"symbol": "LINKETH", "orderId": 153849728, "orderListId": -1,
                       "clientOrderId": "sell-LINKETH-1580093596005686", "transactTime": 1580093596074,
                       "price": "0.00000000", "origQty": "1.00000000", "executedQty": "1.00000000",
                       "cummulativeQuoteQty": "0.01547019", "status": "FILLED", "timeInForce": "GTC", "type": "MARKET",
                       "side": "SELL", "fills": [{"price": "0.01547019", "qty": "1.00000000",
                                                  "commission": "0.00001547", "commissionAsset": "ETH",
                                                  "tradeId": 6034667}]}
