![Hummingbot](https://i.ibb.co/X5zNkKw/blacklogo-with-text.png)

----
[![Jenkins](https://jenkins-02.coinalpha.com/buildStatus/icon?job=hb_test-master_branch&subject=jenkins:master)](https://jenkins-02.coinalpha.com/job/hb_test-master_branch)
[![Jenkins](https://jenkins-02.coinalpha.com/buildStatus/icon?job=hb_test-development_branch&subject=:development)](https://jenkins-02.coinalpha.com/job/hb_test-development_branch)
[![Discord](https://img.shields.io/discord/530578568154054663.svg?color=768AD4&label=discord&logo=https%3A%2F%2Fdiscordapp.com%2Fassets%2F8c9701b98ad4372b58f13fd9f65f966e.svg)](https://discord.hummingbot.io/)
[![License](https://img.shields.io/badge/License-Apache%202.0-informational.svg)](https://github.com/CoinAlpha/hummingbot/blob/master/LICENSE)
[![Twitter Follow](https://img.shields.io/twitter/follow/hummingbot_io.svg?style=social&label=hummingbot)](https://twitter.com/hummingbot_io)

Hummingbot is an open-source project that integrates cryptocurrency trading on both **centralized exchanges** and **decentralized protocols**. It allows users to run a client that executes customized, automated trading strategies for cryptocurrencies.

We created hummingbot to promote **decentralized market-making**: enabling members of the community to contribute to the liquidity and trading efficiency in cryptocurrency markets.

## Connector status

![GREEN](https://via.placeholder.com/15/008000/?text=+) GREEN - Connector is working properly and safe to use

![YELLOW](https://via.placeholder.com/15/ffff00/?text=+) YELLOW - Connector is either new or has one or more issues

![RED](https://via.placeholder.com/15/f03c15/?text=+) RED - Connector is broken and unusable


## Supported centralized exchanges

| logo | id | name | ver | doc | status |
|:---:|:---:|:---:|:---:|:---:|:---:|
| <img src="assets/ascend_ex_logo.png" alt="AscendEx" width="90" /> | ascend_ex | [AscendEx](https://ascendex.com/en/global-digital-asset-platform) | 1 | [API](https://ascendex.github.io/ascendex-pro-api/#ascendex-pro-api-documentation) |![YELLOW](https://via.placeholder.com/15/ffff00/?text=+)  |
| <img src="assets/beaxy_logo.png" alt="Beaxy" width="90" /> | beaxy | [Beaxy](https://beaxy.com/) | 2 | [API](https://beaxyapiv2trading.docs.apiary.io/) |![GREEN](https://via.placeholder.com/15/008000/?text=+)|
| <img src="https://i.ibb.co/m0YDQLd/Screen-Shot-2019-03-14-at-10-53-42-AM.png" alt="Binance" width="90" /> | binance | [Binance](https://www.binance.com/) | 3 | [API](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md) |![GREEN](https://via.placeholder.com/15/008000/?text=+) | 
| <img src="assets/binanceus_logo.png" alt="Binance US" width="90" /> | binance_us | [Binance US](https://www.binance.com/) | 3 | [API](https://github.com/binance-us/binance-official-api-docs/blob/master/rest-api.md) |![YELLOW](https://via.placeholder.com/15/ffff00/?text=+) |
| <img src="assets/binance_perpetual_logo.png" alt="Binance Perpetual" width="90" /> | binance_perpetual | [Binance Futures](https://www.binance.com/) | 1 | [API](https://binance-docs.github.io/apidocs/futures/en/) |![YELLOW](https://via.placeholder.com/15/ffff00/?text=+) |
|<img src="assets/bittrex_logo.png" alt="Bittrex Global" width="90" height="30" />| bittrex | [Bittrex Global](https://global.bittrex.com/) | 3 | [API](https://bittrex.github.io/api/v3) |![YELLOW](https://via.placeholder.com/15/ffff00/?text=+) |
| <img src="assets/bitfinex_logo.png" alt="Bitfinex" width="90" /> | bitfinex | [Bitfinex](https://www.bitfinex.com/) | 2 | [API](https://docs.bitfinex.com/docs/introduction) |![YELLOW](https://via.placeholder.com/15/ffff00/?text=+)  |
| <img src="assets/blocktane_logo.png" alt="Blocktane" width="90" /> | blocktane | [Blocktane](https://blocktane.io/) | 2 | [API](https://blocktane.io/api) |![GREEN](https://via.placeholder.com/15/008000/?text=+)  |
| <img src="https://i.ibb.co/h9JdGDW/cbp.jpg" alt="Coinbase Pro" width="90" /> | coinbase_pro | [Coinbase Pro](https://pro.coinbase.com/) | * | [API](https://docs.pro.coinbase.com/) |![YELLOW](https://via.placeholder.com/15/ffff00/?text=+) |
| <img src="assets/coinzoom_logo.svg" alt="CoinZoom" width="90" /> | coinzoom | [CoinZoom](https://trade.coinzoom.com/landing) | * | [API](https://api-docs.coinzoom.com/) |![YELLOW](https://via.placeholder.com/15/ffff00/?text=+) |
| <img src="assets/cryptocom_logo.png" alt="Crypto.com" width="90" /> | crypto_com | [Crypto.com](https://crypto.com/exchange) | 2 | [API](https://exchange-docs.crypto.com/#introduction) |![YELLOW](https://via.placeholder.com/15/ffff00/?text=+) |
| <img src="assets/digifinex_logo.svg" alt="Digifinex" width="90" /> | digifinex | [Digifinex](https://www.digifinex.com/en-ww) | 3 | [API](https://docs.digifinex.com/en-ww/v3/#introduction) |![YELLOW](https://via.placeholder.com/15/ffff00/?text=+) |
| <img src="assets/dydx_logo.png" alt="dYdX" width="90" /> | dydx | [dYdX](https://dydx.exchange/) | 1 | [API](https://legacy-docs.dydx.exchange/#introduction) |![GREEN](https://via.placeholder.com/15/008000/?text=+) |
| <img src="assets/dydx_logo.png" alt="dYdX Perpetual" width="90" /> | dydx_perpetual | [dYdX Perpetual](https://dydx.exchange/) | 3 | [API](https://docs.dydx.exchange/#general) |![YELLOW](https://via.placeholder.com/15/ffff00/?text=+) |
| <img src="assets/ftx_logo.png" alt="FTX" width="90" /> | ftx | [FTX](https://ftx.com/en) | 1 | [API](https://docs.ftx.com/#overview) |![YELLOW](https://via.placeholder.com/15/ffff00/?text=+) |
| <img src="assets/himalaya_logo.png" alt="Himalaya Exchange" width="90" /> | himalaya | [Himalaya Exchange](https://himalaya.exchange/) | * | [API]() |![RED](https://via.placeholder.com/15/f03c15/?text=+) |
| <img src="assets/hitbtc_logo.png" alt="HitBTC" width="90" /> | hitbtc | [HitBTC](https://hitbtc.com/) | 2 | [API](https://api.hitbtc.com/) | ![GREEN](https://via.placeholder.com/15/008000/?text=+) |
|<img src="assets/huobi_logo.png" alt="Huobi Global" width="90" />| huobi | [Huobi Global](https://www.hbg.com) | 1 | [API](https://huobiapi.github.io/docs/spot/v1/en/) |![GREEN](https://via.placeholder.com/15/008000/?text=+) |
| <img src="assets/kucoin_logo.png" alt="KuCoin" width="90" /> | kucoin | [KuCoin](https://www.kucoin.com/) | 1 | [API](https://docs.kucoin.com/#general) |![GREEN](https://via.placeholder.com/15/008000/?text=+) |
| <img src="assets/kraken_logo.png" alt="Kraken" width="90" /> | kraken | [Kraken](https://www.kraken.com/) | 1 | [API](https://www.kraken.com/features/api) |![GREEN](https://via.placeholder.com/15/008000/?text=+) |
| <img src="assets/liquid_logo.png" alt="Liquid" width="90" /> | liquid | [Liquid](https://www.liquid.com/) | 2 | [API](https://developers.liquid.com/) |![GREEN](https://via.placeholder.com/15/008000/?text=+) |
| <img src="assets/okex_logo.png" alt="OKEx" width="90" /> | okex | [OKEx](https://www.okex.com/) | 3 | [API](https://www.okex.com/docs/en/) |![YELLOW](https://via.placeholder.com/15/ffff00/?text=+) |
| <img src="assets/probit_global_logo.png" alt="Probit Global" width="90" /> | probit | [Probit Global](https://www.probit.com/en-us/) | 1 | [API](https://docs-en.probit.com/docs) |![YELLOW](https://via.placeholder.com/15/ffff00/?text=+) |
| <img src="assets/probit_korea_logo.png" alt="Probit Korea" width="90" /> | probit_kr | [Probit Korea](https://www.probit.kr/en-us/) | 1 | [API](https://docs-en.probit.com/docs) |![YELLOW](https://via.placeholder.com/15/ffff00/?text=+) |


## Supported decentralized exchanges

| logo | id | name | ver | doc| maintainer | status |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| <img src="https://i.ibb.co/1sPt940/Screen-Shot-2019-06-06-at-17-50-04.png" alt="Bamboo Relay" width="90" /> | bamboo_relay | [Bamboo Relay](https://bamboorelay.com/) | 3 | [API](https://sra.bamboorelay.com/) | [dex@bamboorelay.com](mailto:dex@bamboorelay.com) | ![RED](https://via.placeholder.com/15/f03c15/?text=+) |
|<img src="assets/dolomite_logo.png" alt="Dolomite" width="90" />| dolomite | [Dolomite](https://dolomite.io/) | 1 | [API](https://docs.dolomite.io/) | [corey@dolomite.io](mailto:corey@dolomite.io) | ![RED](https://via.placeholder.com/15/f03c15/?text=+) |
| <img src="assets/radar_logo.png" alt="Radar Relay" width="90" height="30" /> | radar_relay | [Radar Relay](https://radarrelay.com/) | 2 | [API](https://developers.radarrelay.com/api/trade-api) | | ![unavailable](https://via.placeholder.com/15/f03c15/?text=+) |
| <img src="assets/loopring_logo.png" alt="Loopring" width="90" /> | loopring | [Loopring](https://loopring.io/) | 3 | [API](https://docs3.loopring.io/en/) | | ![YELLOW](https://via.placeholder.com/15/ffff00/?text=+) |


## Supported protocol exchanges
| logo | id | name | ver | doc| status |
|:---:|:---:|:---:|:---:|:---:|:--:|
| <img src="assets/celo_logo.svg" alt="Celo" width="90" /> | celo | [Celo](https://terra.money/) | * | [SDK](https://celo.org/developers) | ![GREEN](https://via.placeholder.com/15/008000/?text=+) |
| <img src="assets/balancer_logo.svg" alt="Balancer" width="90" height="30" /> | balancer | [Balancer](https://balancer.finance/) | * | [SDK](https://docs.balancer.finance/) | ![GREEN](https://via.placeholder.com/15/008000/?text=+) |
| <img src="assets/perpetual_finance_logo.png" alt="Perpetual Protocol" width="90" /> | perpetual_finance | [Perpetual Protocol](https://perp.fi/) | * | [SDK](https://docs.perp.fi/) | ![YELLOW](https://via.placeholder.com/15/ffff00/?text=+) |
| <img src="assets/terra_logo.png" alt="Terra" width="90" /> | terra | [Terra](https://terra.money/) | * | [SDK](https://docs.terra.money/) | ![GREEN](https://via.placeholder.com/15/008000/?text=+) |
| <img src="assets/uniswap_logo.svg" alt="Uniswap" width="90" height="30" /> | uniswap | [Uniswap](https://uniswap.org/) | 2 | [SDK](https://uniswap.org/docs/v2/) | ![GREEN](https://via.placeholder.com/15/008000/?text=+) |



## Getting Started

### Learn more about Hummingbot

- [Website](https://hummingbot.io)
- [Documentation](https://docs.hummingbot.io)
- [FAQs](https://hummingbot.zendesk.com/hc/en-us/categories/900001272063-Hummingbot-FAQs)

### Install Hummingbot

- [Quickstart guide](https://hummingbot.io/academy/quickstart/)
- [All installation options](https://docs.hummingbot.io/installation/overview/)
- [Installation scripts](./installation/)

### Get support
- Chat with our support team on [Discord](https://discord.hummingbot.io)
- Email us at support@hummingbot.io

### Chat with other traders
- Join our community on [Discord](https://discord.coinalpha.com) or [Reddit](https://www.reddit.com/r/Hummingbot/)
- Follow Hummingbot on [Twitter](https://twitter.com/hummingbot_io)

## Contributions

We welcome contributions from the community:
- **Code and documentation contributions** via [pull requests](https://github.com/CoinAlpha/hummingbot/pulls)
- **Bug reports and feature requests** through [Github issues](https://github.com/CoinAlpha/hummingbot/issues)
- When contributing, please review the [contributing guidelines](CONTRIBUTING.md)

## About us

Hummingbot was created and is maintained by CoinAlpha, Inc. We are [a global team of engineers and traders](https://hummingbot.io/about/).

- **General**: contact us at [dev@hummingbot.io](mailto:dev@hummingbot.io) or join our [Discord server](https://discord.hummingbot.io).
- **Business inquiries**: contact us at [partnerships@hummingbot.io](mailto:partnerships@hummingbot.io).

## Legal

- **License**: Hummingbot is licensed under [Apache 2.0](./LICENSE).
- **Data collection**: read important information regarding [Hummingbot Data Collection](DATA_COLLECTION.md).