---
tags:
- spot exchange connector
---

# `gate_io`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/gate_io)

## ℹ️ Exchange Info

**gate_io** 
[Website](https://www.gate.io/en/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/gate-io/) | [CoinGecko](https://www.coingecko.com/en/exchanges/gate-io)

* API docs: https://www.gate.io/docs/apiv4/en/index.html
* Transaction fees: https://www.gate.io/fee
* Minimum order size: https://support.gate.io/hc/en-us/articles/360000808414-What-is-minimum-order-size-
* Creating API keys: https://support.gate.io/hc/en-us/articles/900000114363-What-are-APIKey-and-APIV4keys-for-

## 👷 Maintenance

* Release added: [0.41.0](/release-notes/0.41.0/) by CoinAlpha
* Maintainer: CoinAlpha

## 🔑 Connection

Run `connect gate_io` in order to enter your API keys:
 
```
Enter your gate_io API key >>>
Enter your gate_io secret key >>>
```

If connection is successful:
```
You are now connected to gate_io.
```

## 🪙 Fees

Hummingbot assumes 0.2% maker fees and 0.2% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/gate_io/gate_io_utils.py#L21)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).