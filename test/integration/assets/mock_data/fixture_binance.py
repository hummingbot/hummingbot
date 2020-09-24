class FixtureBinance:
    # General Exchange Info
    MARKETS = {
        "timezone": "UTC", "serverTime": 1594871960959,
        "rateLimits": [
            {"rateLimitType": "REQUEST_WEIGHT", "interval": "MINUTE", "intervalNum": 1, "limit": 1200},
            {"rateLimitType": "ORDERS", "interval": "SECOND", "intervalNum": 10, "limit": 100},
            {"rateLimitType": "ORDERS", "interval": "DAY", "intervalNum": 1, "limit": 200000}],
        "exchangeFilters": [],
        "symbols":
        [
            {
                "symbol": "ETHBTC", "status": "TRADING",
                "baseAsset": "ETH", "baseAssetPrecision": 8,
                "quoteAsset": "BTC", "quotePrecision": 8, "quoteAssetPrecision": 8,
                "baseCommissionPrecision": 8, "quoteCommissionPrecision": 8,
                "orderTypes": [
                    "LIMIT", "LIMIT_MAKER", "MARKET", "STOP_LOSS_LIMIT", "TAKE_PROFIT_LIMIT"],
                "icebergAllowed": True,
                "ocoAllowed": True,
                "quoteOrderQtyMarketAllowed": True,
                "isSpotTradingAllowed": True,
                "isMarginTradingAllowed": True,
                "filters": [
                    {
                        "filterType": "PRICE_FILTER", "minPrice": "0.00000100",
                        "maxPrice": "100000.00000000", "tickSize": "0.00000100"},
                    {
                        "filterType": "PERCENT_PRICE", "multiplierUp": "5",
                        "multiplierDown": "0.2", "avgPriceMins": 5},
                    {
                        "filterType": "LOT_SIZE", "minQty": "0.00100000",
                        "maxQty": "100000.00000000", "stepSize": "0.00100000"},
                    {
                        "filterType": "MIN_NOTIONAL", "minNotional": "0.00010000",
                        "applyToMarket": True, "avgPriceMins": 5},
                    {
                        "filterType": "ICEBERG_PARTS", "limit": 10},
                    {
                        "filterType": "MARKET_LOT_SIZE", "minQty": "0.00000000",
                        "maxQty": "14907.84524965", "stepSize": "0.00000000"},
                    {
                        "filterType": "MAX_NUM_ORDERS", "maxNumOrders": 200},
                    {
                        "filterType": "MAX_NUM_ALGO_ORDERS", "maxNumAlgoOrders": 5}
                ],
                "permissions": ["SPOT", "MARGIN"]},
            {
                "symbol": "LINKETH", "status": "TRADING", "baseAsset": "LINK",
                "baseAssetPrecision": 8, "quoteAsset": "ETH", "quotePrecision": 8,
                "quoteAssetPrecision": 8, "baseCommissionPrecision": 8, "quoteCommissionPrecision": 8,
                "orderTypes": ["LIMIT", "LIMIT_MAKER", "MARKET", "STOP_LOSS_LIMIT",
                               "TAKE_PROFIT_LIMIT"], "icebergAllowed": True, "ocoAllowed": True,
                "quoteOrderQtyMarketAllowed": True, "isSpotTradingAllowed": True,
                "isMarginTradingAllowed": False,
                "filters": [
                    {
                        "filterType": "PRICE_FILTER", "minPrice": "0.00000100",
                        "maxPrice": "1000.00000000", "tickSize": "0.00000100"},
                    {
                        "filterType": "PERCENT_PRICE", "multiplierUp": "5",
                        "multiplierDown": "0.2", "avgPriceMins": 5},
                    {
                        "filterType": "LOT_SIZE", "minQty": "0.01000000",
                        "maxQty": "90000000.00000000", "stepSize": "0.01000000"},
                    {
                        "filterType": "MIN_NOTIONAL", "minNotional": "0.01000000",
                        "applyToMarket": True, "avgPriceMins": 5},
                    {
                        "filterType": "ICEBERG_PARTS", "limit": 10},
                    {
                        "filterType": "MARKET_LOT_SIZE", "minQty": "0.00000000",
                        "maxQty": "52705.60641168", "stepSize": "0.00000000"},
                    {
                        "filterType": "MAX_NUM_ALGO_ORDERS", "maxNumAlgoOrders": 5},
                    {
                        "filterType": "MAX_NUM_ORDERS", "maxNumOrders": 200}
                ],
                "permissions": ["SPOT"]}
        ]
    }

    # General User Info
    BALANCES = {
        "makerCommission": 10, "takerCommission": 10, "buyerCommission": 0, "sellerCommission": 0,
        "canTrade": True, "canWithdraw": True, "canDeposit": True, "updateTime": 1580009996654,
        "accountType": "SPOT", "balances": [
            {"asset": "BTC", "free": "0.00000000", "locked": "0.00000000"},
            {"asset": "ETH", "free": "0.77377698", "locked": "0.00000000"},
            {"asset": "LINK", "free": "4.99700000", "locked": "0.00000000"}]}

    TRADE_FEES = {
        "tradeFee": [
            {"symbol": "LINKBTC", "maker": 0.0010, "taker": 0.0010},
            {"symbol": "LINKBUSD", "maker": 0.0000, "taker": 0.0010},
            {"symbol": "LINKETH", "maker": 0.0010, "taker": 0.0010},
            {"symbol": "ZRXUSDT", "maker": 0.0010, "taker": 0.0010}], "success": True}

    LISTEN_KEY = {'listenKey': 'lbGBXAh56py6THGEWu84Ma0zikdtzGfwXVujN6sL6q16KKvAOo4eJuftICxX'}

    # User Trade Info
    BUY_MARKET_ORDER = {
        "symbol": "LINKETH", "orderId": 153849723, "orderListId": -1,
        "clientOrderId": "buy-LINKETH-1580093594011279", "transactTime": 1580093594072,
        "price": "0.00000000", "origQty": "1.00000000", "executedQty": "1.00000000",
        "cummulativeQuoteQty": "0.01553045", "status": "FILLED", "timeInForce": "GTC", "type": "MARKET",
        "side": "BUY", "fills": [
            {
                "price": "0.01553045", "qty": "1.00000000",
                "commission": "0.00100000", "commissionAsset": "LINK", "tradeId": 6034666}
        ]}

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

    SELL_MARKET_ORDER = {
        "symbol": "LINKETH", "orderId": 153849728, "orderListId": -1,
        "clientOrderId": "sell-LINKETH-1580093596005686", "transactTime": 1580093596074,
        "price": "0.00000000", "origQty": "1.00000000", "executedQty": "1.00000000",
        "cummulativeQuoteQty": "0.01547019", "status": "FILLED", "timeInForce": "GTC", "type": "MARKET",
        "side": "SELL", "fills": [
            {
                "price": "0.01547019", "qty": "1.00000000",
                "commission": "0.00001547", "commissionAsset": "ETH", "tradeId": 6034667}
        ]}

    WS_AFTER_SELL_1 = {"e": "executionReport", "E": 1580194664553, "s": "LINKETH", "c": "sell-LINKETH-1580194659898896",
                       "S": "SELL", "o": "MARKET", "f": "GTC", "q": "1.00000000", "p": "0.00000000", "P": "0.00000000",
                       "F": "0.00000000", "g": -1, "C": "", "x": "NEW", "X": "NEW", "r": "NONE", "i": 154131675,
                       "l": "0.00000000", "z": "0.00000000", "L": "0.00000000", "n": "0", "N": None, "T": 1580194664552,
                       "t": -1, "I": 314282508, "w": True, "m": False, "M": False, "O": 1580194664552,
                       "Z": "0.00000000", "Y": "0.00000000", "Q": "0.00000000"}

    WS_AFTER_SELL_2 = {"e": "executionReport", "E": 1580194664553, "s": "LINKETH", "c": "sell-LINKETH-1580194659898896",
                       "S": "SELL", "o": "MARKET", "f": "GTC", "q": "1.00000000", "p": "0.00000000", "P": "0.00000000",
                       "F": "0.00000000", "g": -1, "C": "", "x": "TRADE", "X": "FILLED", "r": "NONE", "i": 154131675,
                       "l": "1.00000000", "z": "1.00000000", "L": "0.01522729", "n": "0.00001523", "N": "ETH",
                       "T": 1580194664552, "t": 6040499, "I": 314282509, "w": False, "m": False, "M": True,
                       "O": 1580194664552, "Z": "0.01522729", "Y": "0.01522729", "Q": "0.00000000"}

    BUY_LIMIT_ORDER = {"symbol": "LINKETH", "orderId": 154314008, "orderListId": -1,
                       "clientOrderId": "buy-LINKETH-1580267497008962", "transactTime": 1580267497079,
                       "price": "0.01524661", "origQty": "1.00000000", "executedQty": "1.00000000",
                       "cummulativeQuoteQty": "0.01511937", "status": "FILLED", "timeInForce": "GTC", "type": "LIMIT",
                       "side": "BUY", "fills": [{"price": "0.01511937", "qty": "1.00000000",
                                                 "commission": "0.00100000", "commissionAsset": "LINK",
                                                 "tradeId": 6043839}]}

    SELL_LIMIT_ORDER = {"symbol": "LINKETH", "orderId": 154314012, "orderListId": -1,
                        "clientOrderId": "sell-LINKETH-1580267499003825", "transactTime": 1580267499071,
                        "price": "0.01496818", "origQty": "1.00000000", "executedQty": "1.00000000",
                        "cummulativeQuoteQty": "0.01509565", "status": "FILLED", "timeInForce": "GTC", "type": "LIMIT",
                        "side": "SELL", "fills": [{"price": "0.01509565", "qty": "1.00000000",
                                                   "commission": "0.00001510", "commissionAsset": "ETH",
                                                   "tradeId": 6043840}]}

    LIMIT_MAKER_ERROR = {'code': -2010, 'msg': 'Order would immediately match and take.'}

    GET_DEPOSIT_INFO = {"address": "bnb136ns6lfw4zs5hg4n85vdthaad7hq5m4gtkgf23", "success": True,
                        "addressTag": "104312555", "asset": "BNB",
                        "url": "https://explorer.binance.org/address/bnb136ns6lfw4zs5hg4n85vdthaad7hq5m4gtkgf23"}

    OPEN_BUY_ORDER = {
        "symbol": "LINKETH", "orderId": 154316832, "orderListId": -1,
        "clientOrderId": "buy-LINKETH-1580268987255692", "transactTime": 1580268987325,
        "price": "0.01059657", "origQty": "1.00000000", "executedQty": "0.00000000",
        "cummulativeQuoteQty": "0.00000000", "status": "NEW", "timeInForce": "GTC", "type": "LIMIT",
        "side": "BUY", "fills": []}

    OPEN_SELL_ORDER = {
        "symbol": "LINKETH", "orderId": 154316831, "orderListId": -1,
        "clientOrderId": "sell-LINKETH-1580268987255716", "transactTime": 1580268987313,
        "price": "0.02267846", "origQty": "1.00000000", "executedQty": "0.00000000",
        "cummulativeQuoteQty": "0.00000000", "status": "NEW", "timeInForce": "GTC",
        "type": "LIMIT", "side": "SELL", "fills": []}

    CANCEL_ORDER = {"symbol": "LINKETH", "origClientOrderId": "sell-LINKETH-1580268987255716", "orderId": 154316831,
                    "orderListId": -1, "clientOrderId": "zPV6vRg4lnhT5LlYKxpey3", "price": "0.02267846",
                    "origQty": "1.00000000", "executedQty": "0.00000000", "cummulativeQuoteQty": "0.00000000",
                    "status": "CANCELED", "timeInForce": "GTC", "type": "LIMIT", "side": "SELL"}

    LINKETH_SNAP = {"lastUpdateId": 299745427, "bids": [["0.01548716", "223.00000000"], ["0.01548684", "36.00000000"],
                                                        ["0.01548584", "36.00000000"]],
                    "asks": [["0.01552718", "87.00000000"], ["0.01552730", "69.00000000"],
                             ["0.01552876", "12.00000000"]]}
    ZRXETH_SNAP = {"lastUpdateId": 146902033, "bids": [["0.00127994", "723.00000000"], ["0.00127937", "439.00000000"],
                                                       ["0.00127936", "4106.00000000"]],
                   "asks": [["0.00128494", "1991.00000000"], ["0.00128495", "804.00000000"],
                            ["0.00128500", "400.00000000"]]}

    ORDER_BUY_PRECISION = {"symbol": "LINKETH", "orderId": 154388421, "orderListId": -1,
                           "clientOrderId": "buy-LINKETH-1580289856010707", "transactTime": 1580289856293,
                           "price": "0.00516884", "origQty": "3.00000000", "executedQty": "0.00000000",
                           "cummulativeQuoteQty": "0.00000000", "status": "NEW", "timeInForce": "GTC", "type": "LIMIT",
                           "side": "BUY", "fills": []}

    ORDER_BUY_PRECISION_GET = {"symbol": "LINKETH", "orderId": 154388421, "orderListId": -1,
                               "clientOrderId": "buy-LINKETH-1580289856010707", "price": "0.01447300",
                               "origQty": "3.00000000", "executedQty": "0.00000000",
                               "cummulativeQuoteQty": "0.00000000", "status": "NEW", "timeInForce": "GTC",
                               "type": "LIMIT", "side": "BUY", "stopPrice": "0.00000000", "icebergQty": "0.00000000",
                               "time": 1580289856293, "updateTime": 1580289856293, "isWorking": True,
                               "origQuoteOrderQty": "0.00000000"}

    ORDER_SELL_PRECISION = {"symbol": "LINKETH", "orderId": 154388434, "orderListId": -1,
                            "clientOrderId": "sell-LINKETH-1580289858445415", "transactTime": 1580289858734,
                            "price": "0.05333293", "origQty": "1.00000000", "executedQty": "0.00000000",
                            "cummulativeQuoteQty": "0.00000000", "status": "NEW", "timeInForce": "GTC", "type": "LIMIT",
                            "side": "SELL", "fills": []}

    ORDER_SELL_PRECISION_GET = {"symbol": "LINKETH", "orderId": 154388434, "orderListId": -1,
                                "clientOrderId": "sell-LINKETH-1580289858445415", "price": "0.01627100",
                                "origQty": "1.23000000", "executedQty": "0.00000000",
                                "cummulativeQuoteQty": "0.00000000", "status": "NEW", "timeInForce": "GTC",
                                "type": "LIMIT", "side": "SELL", "stopPrice": "0.00000000", "icebergQty": "0.00000000",
                                "time": 1580289858734, "updateTime": 1580289858734, "isWorking": True,
                                "origQuoteOrderQty": "0.00000000"}
