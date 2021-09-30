---
tags:
- perp exchange connector
---

# `bybit_perpetual`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/development/hummingbot/connector/derivative/bybit_perpetual)

## ℹ️ Exchange Info

**Bybit Perpetual** [Website](https://www.bybit.com/en-US/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/bybit/) | [CoinGecko](https://www.coingecko.com/en/exchanges/bybit)

* API docs: https://bybit-exchange.github.io/docs/inverse/#t-introduction
* Transaction fees: https://help.bybit.com/hc/en-us/articles/360039261154-Taker-s-Fee-and-Maker-s-Rebate-Calculation
* Creating API keys: https://help.bybit.com/hc/en-us/articles/360039749613-How-to-create-a-new-API-key-
* Trading rules: https://www.bybit.com/en-US/contract-rules
* Leverage and margin: https://help.bybit.com/hc/en-us/articles/900003821726-Bybit-USDT-Perpetual-General-FAQ

!!! note "Enable Positions and Orders"
    Ensure that the option **Positions and Orders** is checked when you create your API key.

## 👷 Maintenance

* Release added: [0.44.0](/release-notes/0.44.0/) by CoinAlpha
* Maintainer: CoinAlpha

## 🔑 Connection

Run `connect bybit_perpetual` in order to enter your API keys:
 
```
Enter your Bybit Perpetual API key >>>
Enter your Bybit Perpetual secret key >>>
```

If connection is successful:
```
You are now connected to bybit_perpetual.
```

!!! tip "Testnet available"
    Hummingbot supports the testnet version of this exchange. To connect to the testnet exchange, run `connect bybit_perpetual_testnet` instead.

## 🪙 Fees

Hummingbot assumes -0.025% maker fees and 0.075% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/connector/derivative/bybit_perpetual/bybit_perpetual_utils.py#L15)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).