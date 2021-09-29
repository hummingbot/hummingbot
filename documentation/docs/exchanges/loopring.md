---
tags:
- spot exchange connector
- ethereum dex
---

# `loopring`

## 📁 [Connector folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/loopring)

## ℹ️ Exchange Info

**Loopring** 
[Website](https://loopring.io/) | [CoinMarketCap](https://coinmarketcap.com/exchanges/loopring-exchange/) | [CoinGecko](https://www.coingecko.com/en/exchanges/loopring)

* API docs: https://docs.loopring.io/
* Transaction fees: https://blogs.loopring.org/loopring-exchange-faq/
* Minimum order size: https://docs.loopring.io/en/dex_apis/getOrderUserRateAmount.html?h=minimum%20amount
* Creating API keys: https://blogs.loopring.org/loopring-exchange-faq/#how-do-i-register-an-account

## 👷 Maintenance

* Release added: [0.32.0](/release-notes/0.32.0/) by CoinAlpha
* Maintainer: 

## 🔑 Connection

Since this exchange is an Ethereum-based decentralized exchange (DEX), first run `connect ethereum` in order to connect your Ethereum wallet. See [Ethereum](/protocols/ethereum) for more information. Then, go to dYdX and create API keys for the same Ethereum wallet.

Next, `connect loopring` in Hummingbot in order to enter your API keys:

```
Enter your Loopring account id >>>
Enter the Loopring exchange address >>>
Enter your Loopring private key >>>
Enter your loopring api key >>>
```

If connection is successful:
```
You are now connected to loopring.
```

## 🪙 Fees

Hummingbot assumes 0% maker fees and 0.2% taker fees ([source](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/loopring/loopring_utils.py#L11)).

Users can override these assumptions with [Override Fees](/global-configs/override-fees/).

