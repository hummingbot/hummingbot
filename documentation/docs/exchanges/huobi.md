---
tags:
- spot exchange connector
---

# `huobi`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/huobi)

## ℹ️ Exchange Info

**Huobi Global** 
[Website](https://www.hbg.com/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/huobi-global/) | [CoinGecko](https://www.coingecko.com/en/exchanges/huobi)

* API docs: https://huobiapi.github.io/docs/spot/v1/en/#change-log
* Transaction fees: https://www.hbg.com/en-us/about/fee/
* Minimum order size: https://huobiglobal.zendesk.com/hc/en-us/articles/900000210246-Announcement-on-Adjusting-Minimum-Order-Amount-for-Some-Trading-Pairs
* Creating API keys: https://www.huobi.com/support/en-us/detail/360000203002

## 👷 Maintenance

* Release added: [0.14.0](/release-notes/0.14.0/) by CoinAlpha
* Maintainer: 

## 🔑 Connection

Run `connect huobi` in order to enter your API keys:
 
```
Enter your Huobi API key >>>
Enter your Huobi secret key >>>
```

If connection is successful:
```
You are now connected to huobi.
```

## 🪙 Fees

Hummingbot assumes 0.2% maker fees and 0.2% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/huobi/huobi_utils.py#L22)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).