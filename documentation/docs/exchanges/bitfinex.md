---
tags:
- spot exchange connector
---

# `bitfinex`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/bitfinex)

## ℹ️ Exchange Info

**Bitfinex** 
[Website](https://www.bitfinex.com/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/bitfinex/) | [CoinGecko](https://www.coingecko.com/en/exchanges/bitfinex)

* API docs: https://docs.bitfinex.com/docs/introduction
* Transaction fees: https://www.bitfinex.com/fees/
* Minimum order size: https://support.bitfinex.com/hc/en-us/articles/115003283709-What-is-the-minimum-order-size-on-Bitfinex-
* Creating API keys: https://support.bitfinex.com/hc/en-us/articles/115003363429-How-to-create-and-revoke-a-Bitfinex-API-Key-

## 👷 Maintenance

* Release added: [0.32.0](/release-notes/0.32.0/) by CoinAlpha
* Maintainer: 

## 🔑 Connection

Run `connect bitfinex` in order to enter your API keys:
 
```
Enter your Bitfinex API key >>>
Enter your Bitfinex secret key >>>
```

If connection is successful:
```
You are now connected to bitfinex.
```

## 🪙 Fees

Hummingbot assumes 0.1% maker fees and 0.2% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/bitfinex/bitfinex_utils.py#L20)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).