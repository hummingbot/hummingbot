---
tags:
- spot exchange connector
---

# `probit`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/probit)

## ℹ️ Exchange Info

**Probit Global** 
[Website](https://www.probit.com/en-us/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/probit-exchange/) | [CoinGecko](https://www.coingecko.com/en/exchanges/probit)

* API docs: https://docs-en.probit.com/docs
* Transaction fees: https://support.probit.com/hc/en-us/articles/360017844972-Trading-Fee-Structure-at-ProBit
* Minimum order size: 
* Creating API keys: https://docs-en.probit.com/docs/managing-withdrawal-api

## 👷 Maintenance

* Release added: [0.37.0](/release-notes/0.37.0/) by CoinAlpha
* Maintainer: 

## 🔑 Connection

Run `connect probit` in order to enter your API keys:
 
```
Enter your ProBit Client ID >>>
Enter your ProBit secret key >>>
```

If connection is successful:
```
You are now connected to probit.
```

## 🪙 Fees

Hummingbot assumes 0.2% maker fees and 0.2% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/probit/probit_utils.py#L24)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).