---
tags:
- spot exchange connector
---

# `blocktane`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/blocktane)

## ℹ️ Exchange Info

**Blocktane** 
[Website](https://blocktane.io/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/blocktane/)

* API docs: https://blocktane.io/api
* Transaction fees: https://help.blocktane.io/fees-limits
* Minimum order size: https://help.blocktane.io/fees-limits
* Creating API keys: https://help.blocktane.io/api-getting-started

## 👷 Maintenance

* Release added: [0.36.0](/release-notes/0.36.0/) by CoinAlpha
* Maintainer: CoinAlpha

## 🔑 Connection

Run `connect blocktane` in order to enter your API keys:
 
```
Enter your Blocktane API key >>>
Enter your Blocktane API secret >>>
```

If connection is successful:
```
You are now connected to blocktane.
```

## 🪙 Fees

Hummingbot assumes 0.35% maker fees and 0.45% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/blocktane/blocktane_utils.py#L12)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).