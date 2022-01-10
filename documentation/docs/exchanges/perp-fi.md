---
tags:
- amm exchange connector
- ethereum dex
---

# `perp_fi`

!!! note
    This connector supports a deprecated version of Perpetual Protocol on the xDAI blockchain. This connector will be refactored as part of the [Gateway V2 redesign](/developers/gateway) and will be updated to support Perpetual Protocol on the Arbitrum blockchain afterwards.

## 📁 Folders

* [Gateway - Routes](https://github.com/CoinAlpha/gateway-api/blob/master/src/routes/perpetual_finance.route.js)
* [Gateway - Service](https://github.com/CoinAlpha/gateway-api/blob/master/src/services/perpetual_finance.js)

## ℹ️ Exchange Info

**Perpetual Protocol** 
[Website](https://perp.fi/) | [CoinMarketCap](https://coinmarketcap.com/currencies/perpetual-protocol/) | [CoinGecko](https://www.coingecko.com/en/coins/perpetual-protocol)

* API docs: https://docs.perp.fi/
* Fees: https://docs.perp.fi/faqs/trading-faq#what-are-the-fees-charged-by-perpetual-protocol-when-trading

## 👷 Maintenance

* Release added: [0.37.0](/release-notes/0.37.0/) by CoinAlpha
* Maintainer: CoinAlpha

## 🔑 Connection

## 🔑 Connection

First, follow the instructions to install and run [Hummingbot Gateway](/protocols/gateway/).

Since this exchange is an xDAI-based decentralized exchange (DEX), run `connect xdai` in order to connect your wallet to the xDAI blockchain.
