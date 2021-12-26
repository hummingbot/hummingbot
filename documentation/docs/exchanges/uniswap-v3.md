---
tags:
- amm exchange connector
- ethereum dex
---

# `uniswap_v3`

!!! note
    This connector is currently being refactored as part of the [Gateway V2 redesign](/developers/gateway). The current V1 version is working, but may have usability issues that will be addressed in the redesign.

## 📁 Folders

* [Hummingbot - Connector](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/connector/uniswap_v3)
* [Gateway - Routes](https://github.com/CoinAlpha/gateway-api/blob/master/src/routes/uniswap_v3.ts)
* [Gateway - Service](https://github.com/CoinAlpha/gateway-api/blob/master/src/services/uniswap_v3.js)


## ℹ️ Exchange Info

Note that this connector integrates with [Uniswap V3](https://docs.uniswap.org/protocol/introduction), which introduces concentrated liquidity and multiple fee tiers as new features, giving liquidity providers more control.

**Uniswap** 
[Website](https://uniswap.org/) | [CoinMarketCap](https://coinmarketcap.com/currencies/terra-luna/) | [CoinGecko](https://www.coingecko.com/en/coins/uniswap)

* API docs: https://docs.uniswap.org/protocol/introduction
* SDK: https://docs.uniswap.org/sdk/introduction
* Fees: https://docs.uniswap.org/protocol/concepts/V3-overview/fees

## 👷 Maintenance

* Release added: [0.40.0](/release-notes/0.40.0/) by CoinAlpha
* Maintainer: CoinAlpha

## 🔑 Connection

First, follow the instructions to install and run [Hummingbot Gateway](/protocols/gateway/).

Since this exchange is an Ethereum-based decentralized exchange (DEX), run `connect ethereum` in order to connect your Ethereum wallet. See [Ethereum](/protocols/ethereum) for more information.

