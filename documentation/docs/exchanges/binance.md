---
tags:
- spot exchange connector
- ⛏️ liquidity mining exchange
---

# `binance`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/binance)

## ℹ️ Exchange Info

**Binance.com** [Website](https://binance.com/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/binance/) | [CoinGecko](https://www.coingecko.com/en/exchanges/binance)

* API docs: https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md
* Transaction fees: https://www.binance.com/en/fee/schedule
* Minimum order size: https://www.binance.com/en/trade-rule
* Creating API keys: https://www.binance.com/en/support/faq/360002502072

## 👷 Maintenance

* Release added: [0.2.0](/release-notes/0.2.0/) by CoinAlpha
* Maintainer: CoinAlpha

## 🔑 Connection

Run `connect binance` in order to enter your API keys:
 
```
Enter your Binance API key >>>
Enter your Binance secret key >>>
```

If connection is successful:
```
You are now connected to binance.
```

## 🪙 Fees

Hummingbot assumes 0.1% maker fees and 0.1% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/binance/binance_utils.py#L10)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).
