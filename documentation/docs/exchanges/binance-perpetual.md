---
tags:
- perp exchange connector
---

# `binance_perpetual`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/binance)

## ℹ️ Exchange Info

**Binance.com (Futures)** [Website](https://www.binance.com/en/futures) | [CoinMarketCap](https://coinmarketcap.com/exchanges/binance/) | [CoinGecko](https://www.coingecko.com/en/exchanges/binance)

* API docs: https://binance-docs.github.io/apidocs/futures/en/#change-log
* Transaction fees: https://www.binance.com/en/support/faq/360033544231
* Creating API keys: https://www.binance.com/en/support/faq/360002502072
* Trading rules: https://www.binance.com/en/futures/trading-rules/perpetual
* Leverage and margin: https://www.binance.com/en/support/faq/360033162192

!!! note "Enable Futures"
    Ensure that the option **Enable Futures** is checked when you create your API key. If you don't see this option, you may need to open a Binance Futures account first.

## 👷 Maintenance

* Release added: [0.33.0](/release-notes/0.33.0/) by CoinAlpha
* Maintainer: CoinAlpha

## 🔑 Connection

Run `connect binance_perpetual` in order to enter your API keys:
 
```
Enter your binance_perpetual API key >>>
Enter your binance_perpetual secret key >>>
```

If connection is successful:
```
You are now connected to binance_perpetual.
```

!!! tip "Testnet available"
    Hummingbot supports the testnet version of this exchange. To connect to the testnet exchange, run `connect binance_perpetual_testnet` instead.

## 🪙 Fees

Hummingbot assumes 0.02% maker fees and 0.04% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/derivative/binance_perpetual/binance_perpetual_utils.py#L18)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).
