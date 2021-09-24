---
tags:
- spot exchange connector
---

# `kraken`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/kraken)

## ℹ️ Exchange Info

**Kraken** 
[Website](https://www.kraken.com/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/kraken/) | [CoinGecko](https://www.coingecko.com/en/exchanges/kraken)

* API docs: https://docs.kraken.com/rest/
* Transaction fees: https://www.kraken.com/features/fee-schedule
* Minimum order size: https://support.kraken.com/hc/en-us/articles/205893708-Minimum-order-size-volume-for-trading
* Creating API keys: https://support.kraken.com/hc/en-us/articles/360000919966-How-to-generate-an-API-key-pair-

## 👷 Maintenance

* Release added: [0.26.0](/release-notes/0.26.0/) by CoinAlpha
* Maintainer: 

## 🔑 Connection

Run `connect kraken` in order to enter your API keys:
 
```
Enter your Kraken API key >>>
Enter your Kraken secret key >>>
```

If connection is successful:
```
You are now connected to kraken.
```

## 🪙 Fees

Hummingbot assumes 0.16% maker fees and 0.26% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/kraken/kraken_utils.py#L16)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).