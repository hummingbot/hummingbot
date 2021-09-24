---
tags:
- spot exchange connector
---

# `hitbtc`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/hitbtc)

## ℹ️ Exchange Info

**HitBTC** 
[Website](https://hitbtc.com/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/hitbtc/) | [CoinGecko](https://www.coingecko.com/en/exchanges/hitbtc)

* API docs: https://api.hitbtc.com/
* Transaction fees: https://hitbtc.com/fee-tier
* Minimum order size: https://blog.hitbtc.com/system-updates-lot-size-changes/
* Creating API keys: https://support.hitbtc.com/en/support/solutions/articles/63000225027-hitbtc-api-keys

## 👷 Maintenance

* Release added: [0.38.0](/release-notes/0.38.0/) by CoinAlpha
* Maintainer: 

## 🔑 Connection

Run `connect hitbtc` in order to enter your API keys:
 
```
Enter your hitbtc API key >>>
Enter your hitbtc secret API key >>>
```

If connection is successful:
```
You are now connected to hitbtc.
```

## 🪙 Fees

Hummingbot assumes 0.1% maker fees and 0.25% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/hitbtc/hitbtc_utils.py#L25)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).