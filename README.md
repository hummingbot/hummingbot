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

OKEx is reportedly being investigated by Chinese authorities and has stopped withdrawals.

## Supported centralized exchanges

| logo | id | name | ver | doc | status |
|:---:|:---:|:---:|:---:|:---:|:---:|
| <img src="https://i.ibb.co/m0YDQLd/Screen-Shot-2019-03-14-at-10-53-42-AM.png" alt="Binance" width="90" /> | binance | [Binance](https://www.binance.com/) | 3 | [API](https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md) | ![GREEN](https://via.placeholder.com/15/008000/?text=+) | Connector is working properly
| <img src="https://i.ibb.co/h9JdGDW/cbp.jpg" alt="Coinbase Pro" width="90" /> | coinbase_pro | [Coinbase Pro](https://pro.coinbase.com/) | * | [API](https://docs.pro.coinbase.com/) | ![GREEN](https://via.placeholder.com/15/008000/?text=+) |
|<img src="assets/huobi_logo.png" alt="Huobi Global" width="90" />| huobi | [Huobi Global](https://www.hbg.com) | 1 | [API](https://huobiapi.github.io/docs/spot/v1/en/) | ![GREEN](https://via.placeholder.com/15/008000/?text=+) |
|<img src="assets/bittrex_logo.png" alt="Bittrex Global" width="90" height="30" />| bittrex | [Bittrex Global](https://global.bittrex.com/) | 3 | [API](https://bittrex.github.io/api/v3) | ![YELLOW](https://via.placeholder.com/15/ffff00/?text=+) |
| <img src="assets/liquid_logo.png" alt="Liquid" width="90" /> | liquid | [Liquid](https://www.liquid.com/) | 2 | [API](https://developers.liquid.com/) | ![GREEN](https://via.placeholder.com/15/008000/?text=+) |
| <img src="assets/kucoin_logo.png" alt="KuCoin" width="90" /> | kucoin | [KuCoin](https://www.kucoin.com/) | 1 | [API](https://docs.kucoin.com/#general) | ![GREEN](https://via.placeholder.com/15/008000/?text=+) |
| <img src="assets/kraken_logo.png" alt="Kraken" width="90" /> | kraken | [Kraken](https://www.kraken.com/) | 1 | [API](https://www.kraken.com/features/api) | ![YELLOW](https://via.placeholder.com/15/ffff00/?text=+) |
| <img src="assets/eterbase_logo.png" alt="Eterbase" width="90" /> | eterbase | [Eterbase](https://www.eterbase.com/) | * | [API](https://developers.eterbase.exchange/?version=latest) | ![RED](https://via.placeholder.com/15/f03c15/?text=+) |
| <img src="assets/cryptocom_logo.png" alt="Crypto.com" width="90" /> | crypto_com | [Crypto.com](https://crypto.com/exchange) | 2 | [API](https://exchange-docs.crypto.com/#introduction) | ![YELLOW](https://via.placeholder.com/15/ffff00/?text=+) |
| <img src="assets/bitfinex_logo.png" alt="Bitfinex" width="90" /> | bitfinex | [Bitfinex](https://www.bitfinex.com/) | 2 | [API](https://docs.bitfinex.com/docs/introduction) | ![GREEN](https://via.placeholder.com/15/008000/?text=+)  |
| <img src="assets/okex_logo.png" alt="OKEx" width="90" /> | okex | [OKEx](https://www.okex.com/) | 2 | [API](https://www.okex.com/docs/en/) | ![RED](https://via.placeholder.com/15/f03c15/?text=+) |


## Supported decentralized exchanges

| logo | id | name | ver | doc| status |
|:---:|:---:|:---:|:---:|:---:|:--:|
| <img src="assets/radar_logo.png" alt="Radar Relay" width="90" height="30" /> | radar_relay | [Radar Relay](https://radarrelay.com/) | 2 | [API](https://developers.radarrelay.com/api/trade-api) | ![unavailable](https://via.placeholder.com/15/f03c15/?text=+) |
| <img src="assets/loopring_logo.png" alt="Loopring" width="90" /> | loopring | [Loopring](https://loopring.io/) | * | [API](https://docs.loopring.io/en/) | ![GREEN](https://via.placeholder.com/15/008000/?text=+) |

## Community contributed exchange connectors

| logo | id | name | ver | doc| maintainer | status |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| <img src="https://i.ibb.co/1sPt940/Screen-Shot-2019-06-06-at-17-50-04.png" alt="Bamboo Relay" width="90" /> | bamboo_relay | [Bamboo Relay](https://bamboorelay.com/) | 3 | [API](https://sra.bamboorelay.com/) | [dex@bamboorelay.com](mailto:dex@bamboorelay.com) | ![RED](https://via.placeholder.com/15/f03c15/?text=+) |
|<img src="assets/dolomite_logo.png" alt="Dolomite" width="90" />| dolomite | [Dolomite](https://dolomite.io/) | 1 | [API](https://docs.dolomite.io/) | [corey@dolomite.io](mailto:corey@dolomite.io) | ![RED](https://via.placeholder.com/15/f03c15/?text=+) |


## Getting Started

### Learn more about Hummingbot

- [Website](https://hummingbot.io)
- [Documentation](https://docs.hummingbot.io)
- [FAQs](https://docs.hummingbot.io/faq/)

### Install Hummingbot

- [Quickstart guide](https://docs.hummingbot.io/quickstart/)
- [All installation options](https://docs.hummingbot.io/installation/)
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