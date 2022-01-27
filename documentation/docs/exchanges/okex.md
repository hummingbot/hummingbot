---
tags:
- spot exchange connector
---

# `okex`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/okex)

## ℹ️ Exchange Info

**OKEx** 
[Website](https://www.okex.com/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/okex/) | [CoinGecko](https://www.coingecko.com/en/exchanges/okex)

* API docs: https://www.okex.com/docs/en/
* Transaction fees: https://www.okex.com/fees.html
* Minimum order size: https://www.okex.com/support/hc/en-us/articles/360059776832-OKEx-to-adjust-minimum-order-amounts-for-some-spot-and-margin-trading-pairs
* Creating API keys: https://www.okex.com/academy/en/complete-guide-to-okex-api-v5-upgrade

## 👷 Maintenance

* Release added: [0.33.0](/release-notes/0.33.0/) by CoinAlpha
* Maintainer: 

## 🔑 Connection

Run `connect okex` in order to enter your API keys:
 
```
Enter your OKEx API key >>>
Enter your OKEx secret key >>>
Enter your OKEx passphrase key >>>
```

If connection is successful:
```
You are now connected to okex.
```

## 🪙 Fees

Hummingbot assumes 0.1% maker fees and 0.15% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/okex/okex_utils.py#L12)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).
