---
tags:
- spot exchange connector
---

# `MEXC Global`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/mexc)

## ℹ️ Exchange Info

**MEXC Global**
[Website](https://www.mexc.com/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/mxc/) | [CoinGecko](https://www.coingecko.com/en/exchanges/mexcglobal)

* API docs: https://mxcdevelop.github.io/APIDoc/
* Transaction fees: https://www.mexc.com/fee
* Minimum order size: https://www.mexc.com/fee
* Creating API keys: https://support.mexc.com/hc/en-001/articles/360055933652

## 👷 Maintenance

* Release added: [0.46.0](/release-notes/0.46.0/) by CoinAlpha
* Maintainer: 

## 🔑 Connection

Run `connect mexc` in order to enter your API keys:

```
Enter your MEXC API key >>>
Enter your MEXC secret API key >>>
```

If connection is successful:
```
You are now connected to MEXC.
```

## 🪙 Fees

Hummingbot assumes 0.2% maker fees and 0.2% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/mexc/mexc_utils.py#L15)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).
