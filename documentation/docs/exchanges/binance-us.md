---
tags:
- spot exchange connector
---

# `binance_us`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/binance)

!!! note
    Since their APIs are identical, `binance_us` uses the same connector folder as [`binance`](../binance). See [`binance.utils.py`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/binance/binance_utils.py#L60) for information related to Binance.US.

## ℹ️ Exchange Info

**Binance.US** [Website](https://binance.us/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/binance-us/) | [CoinGecko](https://www.coingecko.com/en/exchanges/binance_us)

* API docs: https://github.com/binance-us/binance-official-api-docs/blob/master/rest-api.md
* Transaction fees: https://www.binance.us/en/fee/schedule
* Minimum order size: https://www.binance.us/en/trade-rule
* Creating API keys: https://www.binance.com/en/support/faq/360002502072

## 👷 Maintenance

* Release added: [0.33.0](/release-notes/0.33.0/) by CoinAlpha
* Maintainer: CoinAlpha

## 🔑 Connection

Run `connect binance_us` in order to enter your API keys:
 
```
Enter your Binance US API key >>>
Enter your Binance US secret key >>>
```

If connection is successful:
```
You are now connected to binance_us.
```

## 🪙 Fees

Hummingbot assumes 0.1% maker fees and 0.1% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/binance/binance_utils.py#L63)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).
