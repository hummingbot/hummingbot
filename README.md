# Hummingbot - *Decentralize Market Making*

[![CircleCI](https://circleci.com/gh/CoinAlpha/hummingbot.svg?style=svg&circle-token=c9c4825f21e34926ac8a406eeb260ddee0f726ff)](https://circleci.com/gh/CoinAlpha/hummingbot)
[![Discord](https://img.shields.io/discord/530578568154054663.svg?color=768AD4&label=discord&logo=https%3A%2F%2Fdiscordapp.com%2Fassets%2F8c9701b98ad4372b58f13fd9f65f966e.svg)](https://discord.hummingbot.io/)
[![License](https://img.shields.io/badge/License-Apache%202.0-informational.svg)](https://github.com/CoinAlpha/hummingbot/blob/master/LICENSE)
[![Twitter Follow](https://img.shields.io/twitter/follow/hummingbot_io.svg?style=social&label=hummingbot)](https://twitter.com/hummingbot_io)

An open-source project for the development of cryptocurrency trading software, created and maintained by [CoinAlpha, Inc](https://coinalpha.com).  
#### [Install](https://docs.hummingbot.io/installation/) · [Documentation](https://docs.hummingbot.io/) · [FAQ](https://docs.hummingbot.io/faq-general/) · [Contributing](./CONTRIBUTING.md) · [Blog]()

![CLI View](https://documentation.hummingbot.io/img/hummingbot-cli.png)

Hummingbot allows users to run a local client that executes customized, automated market-making trading strategies for cryptocurrencies.

Hummingbot was created to promote  ***decentralized market-making***: enabling members of the community to contribute to the liquidity and trading efficiency in cryptocurrency markets.  We further discuss this rational on our [blog](https://www.hummingbot.io/blog/2019-01-thin-crust-of-liquidity/).

For more detailed information, please visit the [Hummingbot website](https://hummingbot.io) and read the [Hummingbot whitepaper](https://hummingbot.io/whitepaper.pdf).

## Currently supported cryptocurrency exchanges

|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;logo&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;                                            | id          | name                                                         | ver | doc                                                                                          |                                                                                                                  
|------------------------------------------------------------------------------------------------------------------------------|-------------|:------------------------------------------------------------:|:---:|----------------------------------------------------------------------------------------------|
|[![binance](https://i.ibb.co/m0YDQLd/Screen-Shot-2019-03-14-at-10-53-42-AM.png)](https://www.binance.com/?ref=10205187)       | binance     | [Binance](https://www.binance.com/)                          | *   | [API](https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md) |  
|[![Radar Relay](https://i.ibb.co/7RW75mf/Screen-Shot-2019-03-14-at-10-47-07-AM.png)](https://radarrelay.com/)                        | radar_relay | [Radar Relay](https://radarrelay.com/)                       | 2   | [API](https://developers.radarrelay.com/api/trade-api)                                       | 
|[![DDEX](https://i.ibb.co/Lrpps2G/Screen-Shot-2019-03-14-at-10-39-23-AM.png)](https://ddex.io/)                               | ddex        | [DDEX](https://ddex.io/)                                     | 3   | [API](https://docs.ddex.io/)                                                                 | 

## Resources / links
- [Hummingbot Home Page](https://hummingbot.io)
- [Whitepaper](https://hummingbot.io/whitepaper.pdf)
- [Documentation](https://docs.hummingbot.io)

## Getting started

- Option 1) Clone this repo and [build from source](https://documentation.hummingbot.io/installation/#option-1-run-hummingbot-using-docker)
- Option 2) [Run using Docker](https://documentation.hummingbot.io/installation/#option-2-install-from-source)

## Docker / deployment

Hummingbot is available on Docker Hub at [coinalpha/hummingbot](https://cloud.docker.com/u/coinalpha/repository/docker/coinalpha/hummingbot).

For instructions on running `hummingbot` with Docker including deployment, see [DOCKER.md](DOCKER.md).

## Testing

### Running tests locally

Run tests by executing: `python test/test_**TEST_NAME**.py`.

Requires secret files to be saved in the [hummingbot/templates/test_templates/](hummingbot/templates/test_templates/) folder:

File | Description
---|---
`binance_secret.py` | [binance_secret_TEMPLATE.py](hummingbot/templates/test_templates/binance_secret_TEMPLATE.py)
`web3_wallet_secret.py` | [web3_wallet_secret_TEMPLATE.py](hummingbot/templates/test_templates/web3_wallet_secret_TEMPLATE.py)

## Social / discuss
- [Follow us on Twitter](https://twitter.com/hummingbot_io)
- [Read our blog](https://www.hummingbot.io/blog)
- Join the CoinAlpha / Hummingbot community on our [Discord Server](https://discord.coinalpha.com)

## Contributions are welcome!

We welcome code contributions (via [pull requests](./pulls)) as well as bug reports and feature requests through [github issues](./issues).

When doing so, please review the [contributing guidelines](CONTRIBUTING.md) / git workflow.

## License
Code is released under the [Apache-2.0 License](LICENSE), which means it's absolutely free for any developer to build commercial and opensource software on top of it, but use it at your own risk with no warranties, as is.

## Contact
Hummingbot was created and is maintained by [CoinAlpha](https://www.coinalpha.com). You can contact us at [dev@coinalpha.com](mailto:dev@coinalpha.com) or join our [Discord server](https://discord.coinalpha.com).

For business inquiries, please contact us at [partnerships@hummingbot.io](mailto:partnerships@hummingbot.io).
