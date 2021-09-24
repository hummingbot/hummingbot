---
tags:
- spot exchange connector
---

# `beaxy`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/beaxy)

## ℹ️ Exchange Info

**Beaxy** 
[Website](https://beaxy.com/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/beaxy/) | [CoinGecko](https://www.coingecko.com/en/exchanges/beaxy)

* API docs: https://beaxyapiv2.docs.apiary.io/
* Transaction fees: https://beaxy.com/faq/what-is-the-fee-structure/
* Minimum order size: https://beaxy.com/faq/what-are-the-market-trading-rules/
* Creating API keys: 

## 👷 Maintenance

* Release added: [0.37.0](/release-notes/0.37.0) by CoinAlpha
* Maintainer: 

## 🔑 Connection

Run `connect beaxy` in order to enter your API keys:
 
```
Enter your Beaxy API key >>>
Enter your Beaxy secret API key >>>
```

If connection is successful:
```
You are now connected to beaxy.
```

## 🪙 Fees

Hummingbot assumes 0.15% maker fees and 0.25% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/beaxy/beaxy_utils.py#L11)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).

