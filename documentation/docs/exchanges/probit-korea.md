---
tags:
- spot exchange connector
---

# `probit_kr`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/probit)

## ℹ️ Exchange Info

**Probit Korea** 
[Website](https://www.probit.kr/en-us/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/probit-korea/) | [CoinGecko](https://www.coingecko.com/en/exchanges/probit_kr)

* API docs: https://docs-en.probit.com/docs
* Transaction fees: https://support.probit.com/hc/en-us/articles/360017844972-Trading-Fee-Structure-at-ProBit
* Minimum order size: 
* Creating API keys: https://docs-en.probit.com/docs/managing-withdrawal-api

## 👷 Maintenance

* Release added: [0.37.0](/release-notes/0.37.0/) by CoinAlpha
* Maintainer: 

## 🔑 Connection

Run `connect probit_kr` in order to enter your API keys:
 
```
Enter your ProBit KR Client ID >>>
Enter your ProBit KR secret key >>>
```

If connection is successful:
```
You are now connected to probit_kr.
```

## 🪙 Fees

Hummingbot assumes 0.2% maker fees and 0.2% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/probit/probit_utils.py#L93)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).