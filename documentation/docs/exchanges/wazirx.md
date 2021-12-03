---
tags:
- spot exchange connector
---

# `WazirX`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/wazirx)

## ℹ️ Exchange Info

**WazirX**
[Website](https://wazirx.com/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/wazirx/) | [CoinGecko](https://www.coingecko.com/en/exchanges/wazirx)

* API docs: https://docs.wazirx.com/#public-rest-api-for-wazirx
* Transaction fees: https://wazirx.com/fees
* Minimum order size: https://wazirx.com/fees
* Creating API keys: https://wazirx.com/settings/keys

## 👷 Maintenance

* Release added: [0.46.0](/release-notes/0.46.0/) by CoinAlpha
* Maintainer:

## 🔑 Connection

Run `connect wazirx` in order to enter your API keys:

```
Enter your WazirX API key >>>
Enter your WazirX secret API key >>>
```

If connection is successful:
```
You are now connected to WazirX.
```

## 🪙 Fees

Hummingbot assumes 0.1% maker fees and 0.1% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/wazirx/wazirx_utils.py#L15)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).
