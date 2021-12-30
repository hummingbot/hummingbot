---
tags:
- amm exchange connector
- ethereum dex
---

# `balancer`

!!! note
    This connector is currently being refactored as part of the [Gateway V2 redesign](/developers/gateway). The current V1 version is working, but may have usability issues that will be addressed in the redesign.

## 📁 Folders

* [Hummingbot - Connector](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/connector/balancer)
* [Gateway - Routes](https://github.com/CoinAlpha/gateway-api/blob/master/src/routes/balancer.route.ts)
* [Gateway - Service](https://github.com/CoinAlpha/gateway-api/blob/master/src/services/balancer.js)

## ℹ️ Exchange Info

**Uniswap** 
[Website](https://balancer.fi/) | [CoinMarketCap](https://coinmarketcap.com/currencies/balancer/) | [CoinGecko](https://www.coingecko.com/en/coins/balancer)

* API docs: https://docs.balancer.fi/v/v1/

## 👷 Maintenance

* Release added: [0.33.0](/release-notes/0.33.0/) by CoinAlpha
* Maintainer: CoinAlpha

## 🔑 Connection

First, follow the instructions to install and run [Hummingbot Gateway](/protocols/gateway/).

Since this exchange is an Ethereum-based decentralized exchange (DEX), run `connect ethereum` in order to connect your Ethereum wallet. See [Ethereum](/protocols/ethereum) for more information.
