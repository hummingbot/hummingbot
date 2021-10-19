---
tags:
- spot exchange connector
---

# `coinzoom`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/coinzoom)

## ℹ️ Exchange Info

**Coinzoom** 
[Website](https://www.coinzoom.com/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/coinzoom/) | [CoinGecko](https://www.coingecko.com/en/exchanges/coinzoom)

* API docs: https://api-docs.coinzoom.com/
* Transaction fees: https://www.coinzoom.com/fees/
* Minimum order size: 
* Creating API keys: 

## 👷 Maintenance

* Release added: [0.38.0](/release-notes/0.38.0/) by CoinAlpha
* Maintainer: 

## 🔑 Connection

Run `connect coinzoom` in order to enter your API keys:
 
```
Enter your Coinzoom API key >>>
Enter your Coinzoom secret API key >>>
```

If connection is successful:
```
You are now connected to coinzoom.
```

## 🪙 Fees

Hummingbot assumes 0.2% maker fees and 0.26% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/coinzoom/coinzoom_utils.py#L22)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).