---
tags:
- spot exchange connector
---

# `crypto_com`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/crypto_com)

## ℹ️ Exchange Info

**Crypto.com** 
[Website](https://crypto.com/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/crypto-com-exchange/) | [CoinGecko](https://www.coingecko.com/en/exchanges/crypto_com)

* API docs: https://exchange-docs.crypto.com/spot/index.html#introduction
* Transaction fees: https://crypto.com/exchange/document/fees-limits
* Minimum order size: https://blog.crypto.com/buy-as-little-as-usd-1-of-any-crypto/
* Creating API keys: https://help.crypto.com/en/articles/3511424-api

## 👷 Maintenance

* Release added: [0.31.0](/release-notes/0.31.0/) by CoinAlpha
* Maintainer: 

## 🔑 Connection

Run `connect crypto_com` in order to enter your API keys:
 
```
Enter your Crypto_com API key >>>
Enter your Crypto_com secret API key >>>
```

If connection is successful:
```
You are now connected to crypto_com.
```

## 🪙 Fees

Hummingbot assumes 0.1% maker fees and 0.1% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/crypto_com/crypto_com_utils.py#L15)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).

