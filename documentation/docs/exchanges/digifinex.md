---
tags:
- spot exchange connector
---

# `digifinex`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/digifinex)

## ℹ️ Exchange Info

**Digifinex** 
[Website](https://www.digifinex.com/vi-vn) | [CoinMarketCap](https://coinmarketcap.com/exchanges/digifinex/) | [CoinGecko](https://www.coingecko.com/en/exchanges/digifinex)

* API docs: https://docs.digifinex.com/en-ww/v3/#introduction
* Transaction fees: https://digifinex.zendesk.com/hc/en-us/articles/360000328422--Contract-List-Fees
* Minimum order size: Equivalent value of 2 USDT
* Creating API keys: https://digifinex.zendesk.com/hc/en-us/articles/900002055906--API-How-to-Establish-your-DigiFinex-API-Address-

## 👷 Maintenance

* Release added: [0.38.0](/release-notes/0.38.0/) by CoinAlpha
* Maintainer:

## 🔑 Connection

Run `connect digifinex` in order to enter your API keys:
 
```
Enter your Digifinex API key >>>
Enter your Digifinex secret key >>>
```

If connection is successful:
```
You are now connected to digifinex.
```

## 🪙 Fees

Hummingbot assumes 0.1% maker fees and 0.1% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/digifinex/digifinex_utils.py#L15)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).