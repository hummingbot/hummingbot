---
tags:
- spot exchange connector
---

# `ftx`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/ftx)

## ℹ️ Exchange Info

**ftx** 
[Website](https://ftx.com/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/ftx/) | [CoinGecko](https://www.coingecko.com/en/exchanges/ftx_spot)

* API docs: https://docs.ftx.com/#overview
* Transaction fees: https://help.ftx.com/hc/en-us/articles/360024479432-Fees
* Minimum order size: https://help.ftx.com/hc/en-us/articles/360027946651-Order-Limits-and-Price-Bands
* Creating API keys: https://help.ftx.com/hc/en-us/articles/360028807171-API-docs

## 👷 Maintenance

* Release added: [0.39.0](/release-notes/0.39.0/) by CoinAlpha
* Maintainer:

## 🔑 Connection

Run `connect ftx` in order to enter your API keys:
 
```
Enter your FTX API key >>>
Enter your FTX API secret >>>
```

If connection is successful:
```
You are now connected to ftx.
```

## 🪙 Fees

Hummingbot assumes 0.02% maker fees and 0.07% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/ftx/ftx_utils.py#L15)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).