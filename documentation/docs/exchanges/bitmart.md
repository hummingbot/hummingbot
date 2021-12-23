---
tags:
- spot exchange connector
---

# `bitmart`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/development/hummingbot/connector/exchange/bitmart)

## ℹ️ Exchange Info

**BitMart**
[Website](https://www.bitmart.com/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/bitmart/) | [CoinGecko](https://www.coingecko.com/en/exchanges/bitmart)

- API docs: https://developer-pro.bitmart.com/en/
- Transaction fees: https://support.bmx.fund/hc/en-us/articles/360002043633-Fees
- Minimum order size: 
- Creating API keys: https://support.bmx.fund/hc/en-us/articles/360016076854-How-to-Create-An-API

## 👷 Maintenance

- Release added: [0.44.0](/release-notes/0.44.0/) by CoinAlpha
- Maintainer:

## 🔑 Connection

Run `connect bitmart` in order to enter your API keys:

```
Enter your BitMart API key >>>
Enter your BitMart secret key >>>
Enter your BitMart API Memo >>>
```

If connection is successful:
```
You are now connected to bitmart.
```

## 🪙 Fees

Hummingbot assumes 0.25% maker fees and 0.25% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/connector/exchange/bitmart/bitmart_utils.py#L17)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).
