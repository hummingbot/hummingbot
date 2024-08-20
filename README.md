![Hummingbot](https://i.ibb.co/X5zNkKw/blacklogo-with-text.png)

----
[![License](https://img.shields.io/badge/License-Apache%202.0-informational.svg)](https://github.com/hummingbot/hummingbot/blob/master/LICENSE)
[![Twitter](https://img.shields.io/twitter/url?url=https://twitter.com/_hummingbot?style=social&label=_hummingbot)](https://twitter.com/_hummingbot)
[![Youtube](https://img.shields.io/youtube/channel/subscribers/UCxzzdEnDRbylLMWmaMjywOA)](https://www.youtube.com/@hummingbot)
[![Discord](https://img.shields.io/discord/530578568154054663?logo=discord&logoColor=white&style=flat-square)](https://discord.gg/hummingbot)

Hummingbot is an open source  framework that helps you build automated trading strategies, or **bots** that run on cryptocurrency exchanges.

This code is free and publicly available under the Apache 2.0 open source license!

## Why Hummingbot?

* **Both CEX and DEX connectors**: Hummingbot supports connectors to centralized exchanges like Binance and KuCoin, as well as decentralized exchanges like Uniswap and PancakeSwap on various blockchains (Ethereum, BNB Chain, etc).
* **Cutting edge strategy framework**: Our new V2 Strategies framework allows you to compose powerful, backtestable, multi-venue, multi-timeframe stategies of any type
* **Secure local client**: Hummingbot is a local client software that you install and run on your own devices or cloud virtual machines. It encrypts your API keys and private keys and never exposes them to any third parties.
* **Community focus**: Hummingbot is driven by a global community of quant traders and developers who maintain the connectors and contribute strategies to the codebase.

Help us **democratize high-frequency trading** and make powerful trading algorithms accessible to everyone in the world!


## Quick Links

* [Website and Docs](https://hummingbot.org): Official Hummingbot website and documentation
* [Installation](https://hummingbot.org/installation/docker/): Install Hummingbot on various platforms
* [FAQs](https://hummingbot.org/faq/): Answers to all your burning questions
* [Botcamp](https://hummingbot.org/botcamp/): Learn how to build your own custom HFT strategy in Hummingbot with our hands-on bootcamp!
* [Newsletter](https://hummingbot.substack.com): Get our monthly newsletter whenever we ship a new release
* [Discord](https://discord.gg/hummingbot): The main gathering spot for the global Hummingbot community
* [YouTube](https://www.youtube.com/c/hummingbot): Videos that teach you how to get the most of of Hummingbot
* [Twitter](https://twitter.com/_hummingbot): Get the latest announcements about Hummingbot
* [Snapshot](https://snapshot.org/#/hbot-prp.eth): Participate in monthly polls that decide which components should be prioritized 

## Getting Started

### Install with Docker

We recommend installing Hummingbot using Docker if you want the simplest, easiest installation method and don't need to modify the Hummingbot codebase.


**Prerequisites:**

* MacOS 10.12.6+ / Linux (Ubuntu 20.04+, Debian 10+) / Windows 10+
* Memory: 4 GB RAM per instance
* Storage: 5 GB HDD space per instance
* Install [Docker Compose](https://docs.docker.com/compose/)

```
git clone https://github.com/hummingbot/hummingbot
cd hummingbot
docker compose up -d
docker attach hummingbot
```

### Install from Source

We recommend installing Hummingbot from source if you want to customize or extend the Hummingbot codebase, build new components like connectors or strategies, and/or learn how Hummingbot works at a deeper, technical level.

**Prerequisites:**

* MacOS 10.12.6+ / Linux (Ubuntu 20.04+, Debian 10+)
* Memory: 4 GB RAM per instance
* Storage: 3 GB HDD space per instance
* Install [Anaconda](https://www.anaconda.com/download) or [Miniconda](https://docs.anaconda.com/free/miniconda/miniconda-install/)

```
git clone https://github.com/hummingbot/hummingbot
cd hummingbot
./install
conda activate hummingbot
./compile
./start
```

See [Installation](https://hummingbot.org/installation/linux/) for detailed guides for each OS.

## Architecture

Hummingbot architecture features modular components that can be maintained and extended by individual community members.

### Strategies and Scripts

A Hummingbot strategy is an ongoing process that executes an algorithmic trading strategy. It is constructed as a user-defined program that uses an underlying framework to abstracts low-level operations:

[V2 Strategies](https://hummingbot.org/v2-strategies/): The latest and most advanced way to create strategies in Hummingbot, V2 strategies are built using composable elements known as Controllers and PositionExecutors. These elements can be mixed and matched, offering a modular approach to strategy creation and making the development process faster and more efficient.

[Scripts](https://hummingbot.org/scripts/): For those who are looking for a lightweight solution, Hummingbot provides scripting support. These are single-file strategies that are quick to implement and can be an excellent starting point for those new to algorithmic trading. Check out the [/scripts](https://github.com/hummingbot/hummingbot/tree/master/scripts) folder for all Script examples included in the codebase.

[V1 Strategies](https://hummingbot.org/v1-strategies/): Templatized programs templates for various algorithmic trading strategies that expose a set of user-defined parameters, allowing you to customize the strategy's behavior. While these V1 strategies were Hummingbot's original method of defining strategies and have been superceded by V2 Strategies and Scripts, the strategies below are still often used:

* [Pure Market Making](https://hummingbot.org/strategies/pure-market-making/)
* [Avellaneda Market Making](https://hummingbot.org/strategies/avellaneda-market-making/)
* [Cross-Exchange Market Making](https://hummingbot.org/strategies/cross-exchange-market-making/)

### Connectors

Hummingbot connectors standardize trading logic and order types across different types of exchanges and blockchain networks. Each connector's code is contained in modularized folders in the Hummingbot and/or Gateway codebases.

Currently, the Hummingbot codebase contains 50+ connectors of the following types:

* [CEX](https://hummingbot.org/cex-connectors/): Centralized exchanges take custody of user assets, i.e. Binance, Kucoin, etc.
* [DEX](https://hummingbot.org/dex-connectors/): Decentralized exchanges are platforms in which user assets are stored non-custodially in smart contracts, i.e. dYdX, Uniswap, etc.
* [Chain](https://hummingbot.org/chains/): Layer 1 blockchain ecosystems such as Ethereum, BNB Chain, Avalanche, etc.

Each exchange has one or more connectors in the Hummingbot codebase that supports a specific **market type** that the exchange supports:

 * **spot**: Connectors to central limit order book (CLOB) exchanges that trade spot markets
 * **perp**: Connectors to central limit order book (CLOB) exchanges that trade perpetual swap markets
 * **amm**: Connectors to decentralized exchanges that use the Automatic Market Maker (AMM) methodology

Quarterly [Polls](https://docs.hummingbot.org/governance/polls/) allow HBOT holders decide how maintenance bandwidth and development bounties are allocated toward the connectors in the codebase.

## Sponsors & Partners

The Hummingbot Foundation, supported by its sponsors, partners and backers, is dedicated to fostering a robust, community-driven ecosystem for algorithmic crypto trading.

### Sponsors

- [Vega Protocol](https://vega.xyz/)
- [Hyperliquid](https://hyperliquid.xyz/)
- [CoinAlpha](https://coinalpha.com/)

### Exchange Partners

* [Binance Spot](https://www.binance.com/en/register?ref=FQQNNGCD) | [Binance Futures](https://www.binance.com/en/futures/ref?code=hummingbot)
* [Kucoin](https://www.kucoin.com/ucenter/signup?rcode=272KvRf)
* [Gate.io](https://www.gate.io/signup/5868285)
* [AscendEx](https://ascendex.com/register?inviteCode=UEIXNXKW)
* [Huobi](https://www.htx.com/)
* [OKX](https://www.okx.com/join/1931920)

For more information about the support provided by these partners, see the financial reports provided in [HBOT Tracker](https://docs.google.com/spreadsheets/d/1UNAumPMnXfsghAAXrfKkPGRH9QlC8k7Cu1FGQVL1t0M/edit#gid=285483484).

## Other Hummingbot Repos

* [Dashboard](https://github.com/hummingbot/dashboard): Community pages that help you create, backtest, deploy, and manage Hummingbot instances
* [Gateway](https://github.com/hummingbot/gateway): API middleware for DEX connectors
* [Deploy Examples](https://github.com/hummingbot/deploy-examples): Deploy Hummingbot in various configurations with Docker
* [Hummingbot Site](https://github.com/hummingbot/hummingbot-site): Official documentation for Hummingbot - we welcome contributions here too!
* [Awesome Hummingbot](https://github.com/hummingbot/awesome-hummingbot): All the Hummingbot links
* [Brokers](https://github.com/hummingbot/brokers): Different brokers that can be used to communicate with multiple instances of Hummingbot

## Contributions

Hummingbot belongs to its community, so we welcome contributions! Please review these [guidelines](./CONTRIBUTING.md) first.

To have your exchange connector or other pull request merged into the codebase, please submit a New Connector Proposal or Pull Request Proposal, following these [guidelines](https://hummingbot.org/governance/proposals/). Note that you will need some amount of HBOT tokens in your Ethereum wallet to submit a proposal.

## Legal

* **License**: Hummingbot is licensed under [Apache 2.0](./LICENSE).
* **Data collection**: read important information regarding [Hummingbot Data Collection](./DATA_COLLECTION.md).
