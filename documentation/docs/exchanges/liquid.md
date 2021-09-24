---
tags:
- spot exchange connector
---

# `liquid`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/liquid)

## ℹ️ Exchange Info

**Crypto.com** 
[Website](https://www.liquid.com/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/liquid/) | [CoinGecko](https://www.coingecko.com/en/exchanges/liquid)

* API docs: https://developers.liquid.com/
* Transaction fees: https://www.liquid.com/fees/
* Minimum order size: https://help.liquid.com/en/articles/4141955-liquid-buy-faq
* Creating API keys: https://help.liquid.com/en/articles/2285018-how-to-create-api-tokens

## 👷 Maintenance

* Release added: [0.20.0](/release-notes/0.20.0/) by CoinAlpha
* Maintainer: 

## 🔑 Connection

Run `connect liquid` in order to enter your API keys:
 
```
Enter your Liquid API key >>>
Enter your Liquid secret key >>>
```

If connection is successful:
```
You are now connected to liquid.
```

## 🪙 Fees

Hummingbot assumes 0.1% maker fees and 0.1% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/liquid/liquid_utils.py#L8)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).

