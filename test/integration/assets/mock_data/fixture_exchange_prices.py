class FixtureExchangePrices:

    BINANCE = [
        {"symbol": "ETHBTC", "bidPrice": "0.024", "bidQty": "4.00000000", "askPrice": "0.026", "askQty": "0.90800000"},
        {"symbol": "LTCBTC", "bidPrice": "0.006", "bidQty": "4.00000000", "askPrice": "0.008", "askQty": "0.90800000"},
        {"symbol": "BTCUSDT", "bidPrice": "7000", "bidQty": "4.00000000", "askPrice": "9000", "askQty": "0.90800000"}
    ]

    LIQUID = [
        {"id": "37", "product_type": "CurrencyPair", "code": "CASH", "name": None, "market_ask": 0.024,
         "market_bid": 0.026, "indicator": 1, "currency": "BTC", "currency_pair_code": "ETHBTC", "symbol": "฿",
         "btc_minimum_withdraw": None, "fiat_minimum_withdraw": None, "pusher_channel": "product_cash_ethbtc_37",
         "taker_fee": "0.001", "maker_fee": "0.001", "low_market_bid": "0.025241", "high_market_ask": "0.02667",
         "volume_24h": "375.9444092", "last_price_24h": "0.025481", "last_traded_price": "0.025",
         "last_traded_quantity": "0.020764", "quoted_currency": "BTC", "base_currency": "ETH", "tick_size": "0.000001",
         "disabled": True, "margin_enabled": True, "cfd_enabled": True, "perpetual_enabled": True,
         "last_event_timestamp": "1582972662.084657342", "timestamp": "1582972662.084657342"},
        {"id": "112", "product_type": "CurrencyPair", "code": "CASH", "name": None, "market_ask": 0.006865,
         "market_bid": 0.006826, "indicator": 1, "currency": "BTC", "currency_pair_code": "LTCBTC", "symbol": "฿",
         "btc_minimum_withdraw": None, "fiat_minimum_withdraw": None, "pusher_channel": "product_cash_ltcbtc_112",
         "taker_fee": "0.001", "maker_fee": "0.001", "low_market_bid": "0.006589", "high_market_ask": "0.007145",
         "volume_24h": "1.93906772", "last_price_24h": "0.006702", "last_traded_price": "0.007",
         "last_traded_quantity": "0.72435386", "quoted_currency": "BTC", "base_currency": "LTC",
         "tick_size": "0.000001", "disabled": True, "margin_enabled": True, "cfd_enabled": True,
         "perpetual_enabled": True, "last_event_timestamp": "1582972620.044373769",
         "timestamp": "1582972620.044373769"},
        {"id": "500", "product_type": "CurrencyPair", "code": "CASH", "name": None, "market_ask": 0.00058,
         "market_bid": 0.00057, "indicator": -1, "currency": "ETH", "currency_pair_code": "LINKETH", "symbol": None,
         "btc_minimum_withdraw": None, "fiat_minimum_withdraw": None, "pusher_channel": "product_cash_celeth_500",
         "taker_fee": "0.001", "maker_fee": "0.001", "low_market_bid": "0.00053569", "high_market_ask": "0.000624",
         "volume_24h": "111323.5866001", "last_price_24h": "0.000566", "last_traded_price": "0.00058",
         "last_traded_quantity": "1.0", "quoted_currency": "ETH", "base_currency": "LINK", "tick_size": "0.000001",
         "disabled": True, "margin_enabled": True, "cfd_enabled": True, "perpetual_enabled": True,
         "last_event_timestamp": "1582972653.670587107", "timestamp": "1582972653.670587107"}
    ]

    KUCOIN = {
        "code": "200000", "data": {"ticker": [
            {"symbol": "ETH-BTC", "high": "0.026049", "vol": "8744.78998076", "last": "0.025538", "low": "0.025141",
             "buy": "0.025", "sell": "0.026", "changePrice": "-0.000444", "symbolName": "ETH-BTC",
             "averagePrice": "0.02584302", "changeRate": "-0.017", "volValue": "223.80007890019616"}
        ], "time": 1583116295296}
    }
