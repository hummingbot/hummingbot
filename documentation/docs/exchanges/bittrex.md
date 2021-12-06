---
tags:
- spot exchange connector
---

# `bittrex`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/bittrex)

## ℹ️ Exchange Info

**Bittrex** 
[Website](https://international.bittrex.com/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/bittrex/) | [CoinGecko](https://www.coingecko.com/en/exchanges/bittrex)

* API docs: https://bittrex.github.io/api/v3
* Transaction fees: https://bittrexglobal.zendesk.com/hc/en-us/articles/360009625260
* Minimum order size: https://bittrex.zendesk.com/hc/en-us/articles/360001473863-Bittrex-trading-rules
* Creating API keys: https://bittrex.zendesk.com/hc/en-us/articles/360031921872-How-to-create-an-API-key-

## 👷 Maintenance

* Release added: [0.17.0](/release-notes/0.17.0/) by CoinAlpha
* Maintainer: 

## 🔑 Connection

Run `connect bittrex` in order to enter your API keys:
 
```
Enter your Bittrex API key >>>
Enter your Bittrex secret key >>>
```

If connection is successful:
```
You are now connected to bittrex.
```

## 🪙 Fees

Hummingbot assumes 0.75% maker fees and 0.75% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/bittrex/bittrex_utils.py#L9)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).