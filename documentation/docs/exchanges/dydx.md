---
tags:
- spot exchange connector
---

# `dydx`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/dydx)

## ℹ️ Exchange Info

**dydx** 
[Website](https://dydx.exchange/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/dydx/) | [CoinGecko](https://www.coingecko.com/en/exchanges/dydx-margin)

* API docs: https://docs.dydx.exchange/#general
* Transaction fees: https://help.dydx.exchange/en/articles/4800191-are-there-fees-to-using-dydx
* Minimum order size: Minimum order sizes will vary by trading pair. dYdX has a minimum order of 1 ETH for pairs running with ETH as the base token and 200 DAI for pairs running with DAI as base token.
* Creating API keys: https://docs.dydx.exchange/#get-api-keys

## 👷 Maintenance

* Release added: [0.34.0](/release-notes/0.34.0/) by CoinAlpha
* Maintainer:

## 🔑 Connection

Run `connect dydx` in order to enter your API keys:
 
```
Enter your Ethereum private key >>>
Which Ethereum node would you like your client to connect to? >>>
```

If connection is successful:
```
You are now connected to dydx.
```

## 🪙 Fees

Hummingbot assumes 0.0 maker fees and 0.3% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/dydx/dydx_utils.py#L11)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).