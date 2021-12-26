---
tags:
- spot exchange connector
- ⛏️ liquidity mining exchange
---

# `kucoin`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/kucoin)

## ℹ️ Exchange Info

**KuCoin** 
[Website](https://www.kucoin.com/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/kucoin/) | [CoinGecko](https://www.coingecko.com/en/exchanges/kucoin)

* API docs: https://docs.kucoin.com/#general
* Transaction fees: https://www.kucoin.com/vip/level
* Minimum order size: https://api.kucoin.com/api/v1/symbols
* Creating API keys: https://support.kucoin.plus/hc/en-us/articles/360015102174-How-to-Create-an-API-

## 👷 Maintenance

* Release added: [0.23.0](/release-notes/0.23.0/) by CoinAlpha
* Maintainer: 

## 🔑 Connection

Run `connect kucoin` in order to enter your API keys:
 
```
Enter your KuCoin API key >>>
Enter your KuCoin secret key >>>
Enter your KuCoin passphrase >>>
```

If connection is successful:
```
You are now connected to kucoin.
```

## 🪙 Fees

Hummingbot assumes 0.1% maker fees and 0.1% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/kucoin/kucoin_utils.py#L12)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).