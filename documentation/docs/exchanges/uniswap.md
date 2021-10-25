---
tags:
- amm exchange connector
- ethereum dex
---

# `uniswap`

!!! note
    This connector is currently being refactored as part of the [Gateway V2 redesign](/developers/gateway). The current V1 version is working, but may have usability issues that will be addressed in the redesign.

## 📁 Folders

* [Hummingbot - Connector](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/connector/uniswap)
* [Gateway - Routes](https://github.com/CoinAlpha/gateway-api/blob/master/src/routes/uniswap.ts)
* [Gateway - Service](https://github.com/CoinAlpha/gateway-api/blob/master/src/services/uniswap.js)

## ℹ️ Exchange Info

**Uniswap** 
[Website](https://uniswap.org/) | [CoinMarketCap](https://coinmarketcap.com/currencies/terra-luna/) | [CoinGecko](https://www.coingecko.com/en/coins/uniswap)

* API docs: https://docs.uniswap.org/protocol/V2/introduction
* SDK: https://docs.uniswap.org/sdk/introduction
* Fees: https://docs.uniswap.org/protocol/V2/concepts/advanced-topics/fees

## 👷 Maintenance

* Release added: [0.34.0](/release-notes/0.34.0/) by CoinAlpha
* Maintainer: CoinAlpha

## 🔑 Connection

First, follow the instructions to install and run [Hummingbot Gateway](/protocols/gateway/).

Since this exchange is an Ethereum-based decentralized exchange (DEX), run `connect ethereum` in order to connect your Ethereum wallet. See [Ethereum](/protocols/ethereum) for more information.
