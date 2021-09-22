---
tags:
- spot exchange connector
---

# `coinbase_pro`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/coinbase_pro)

## ℹ️ Exchange Info

**Coinbase Pro** 
[Website](https://pro.coinbase.com/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/coinbase-exchange/) | [CoinGecko](https://www.coingecko.com/en/exchanges/coinbase-exchange)

* API docs: https://docs.pro.coinbase.com/
* Transaction fees: https://help.coinbase.com/en/pro/trading-and-funding/trading-rules-and-fees/fees
* Minimum order size: https://pro.coinbase.com/markets
* Creating API keys: https://help.coinbase.com/en/pro/other-topics/api/how-do-i-create-an-api-key-for-coinbase-pro

## 👷 Maintenance

* Release added: [0.4.0](/release-notes/0.4.0/) by CoinAlpha
* Maintainer: 

## 🔑 Connection

Run `connect coinbase_pro` in order to enter your API keys:
 
```
Enter your Coinbase Pro API key >>>
Enter your Coinbase Pro secret API key >>>
```

If connection is successful:
```
You are now connected to coinbase_pro.
```

## 🪙 Fees

Hummingbot assumes 0.5% maker fees and 0.5% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/coinbase_pro/coinbase_pro_utils.py#L8)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).

