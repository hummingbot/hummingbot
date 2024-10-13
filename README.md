![Hummingbot](https://i.ibb.co/X5zNkKw/blacklogo-with-text.png)

----
[![License](https://img.shields.io/badge/License-Apache%202.0-informational.svg)](https://github.com/hummingbot/hummingbot/blob/master/LICENSE)
[![Twitter](https://img.shields.io/twitter/url?url=https://twitter.com/_hummingbot?style=social&label=_hummingbot)](https://twitter.com/_hummingbot)
[![Youtube](https://img.shields.io/youtube/channel/subscribers/UCxzzdEnDRbylLMWmaMjywOA)](https://www.youtube.com/@hummingbot)
[![Discord](https://img.shields.io/discord/530578568154054663?logo=discord&logoColor=white&style=flat-square)](https://discord.gg/hummingbot)

Hummingbot is an open source framework that helps you design and deploy automated trading strategies, or **bots**, that can run many centralized or decentralized exchange. Over the past year, Hummingbot users have generated over $34 billion in trading volume across 140+ unique trading venues. 

The Hummingbot codebase is free and publicly available under the Apache 2.0 open source license. Our mission is to **democratize high-frequency trading** by creating a global community of algorithmic traders and developers that share knowledge and contribute to the codebase.

## Quick Links

* [Website and Docs](https://hummingbot.org): Official Hummingbot website and documentation
* [Installation](https://hummingbot.org/installation/docker/): Install Hummingbot on various platforms
* [Discord](https://discord.gg/hummingbot): The main gathering spot for the global Hummingbot community
* [YouTube](https://www.youtube.com/c/hummingbot): Videos that teach you how to get the most of of Hummingbot
* [Twitter](https://twitter.com/_hummingbot): Get the latest announcements about Hummingbot
* [Reported Volumes](https://p.datadoghq.com/sb/a96a744f5-a15479d77992ccba0d23aecfd4c87a52): Reported trading volumes across all Hummingbot instances
* [Newsletter](https://hummingbot.substack.com): Get our newsletter whenever we ship a new release



## Supported Exchange Connectors

Hummingbot connectors standardize trading logic and order types across different types of exchanges:

 * **CLOB Spot**: Connectors to spot markets on central limit order book (CLOB) exchanges
 * **CLOB Perp**: Connectors to perpetual futures markets on CLOB exchanges
 * **AMM**: Connectors to spot markets on Automatic Market Maker (AMM) decentralized exchanges

### Partners and Sponsors

We are grateful for the following exchange partners who support the development and maintenance of Hummingbot.

| Connector ID | Exchange | Type | Discount |
|----|------|-------|----------|
| `binance` | [Binance](https://accounts.binance.com/register?ref=CBWO4LU6) | CLOB Spot | [![Sign up for Binance using Hummingbot's referral link for a 10% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d10%25&color=orange)](https://accounts.binance.com/register?ref=CBWO4LU6) |
| `binance_perpetual` | [Binance](https://accounts.binance.com/register?ref=CBWO4LU6) | CLOB Perp | [![Sign up for Binance using Hummingbot's referral link for a 10% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d10%25&color=orange)](https://accounts.binance.com/register?ref=CBWO4LU6) |
| `dydx_v4_perpetual` | [dYdX](https://www.dydx.exchange/) | CLOB Perp | - |
| `hyperliquid_perpetual` | [Hyperliquid](https://hyperliquid.io/) | CLOB Perp | - |
| `gate_io` | [Gate.io](https://www.gate.io/referral/invite/HBOTGATE_0_103) | CLOB Spot | [![Sign up for Gate.io using Hummingbot's referral link for a 10% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d20%25&color=orange)](https://www.gate.io/referral/invite/HBOTGATE_0_103) |
| `gate_io_perpetual` | [Gate.io](https://www.gate.io/referral/invite/HBOTGATE_0_103) | CLOB Perp | [![Sign up for Gate.io using Hummingbot's referral link for a 20% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d20%25&color=orange)](https://www.gate.io/referral/invite/HBOTGATE_0_103) |
| `htx` | [HTX (Huobi)](https://www.htx.com.pk/invite/en-us/1h?invite_code=re4w9223) | CLOB Spot | [![Sign up for HTX using Hummingbot's referral link for a 20% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d20%25&color=orange)](https://www.htx.com.pk/invite/en-us/1h?invite_code=re4w9223) |
| `kucoin` | [KuCoin](https://www.kucoin.com/) | CLOB Spot | - |
| `kucoin_perpetual` | [KuCoin](https://www.kucoin.com/) | CLOB Perp | - |
| `okx` | [OKX](https://www.okx.com/) | CLOB Spot | - |
| `okx_perpetual` | [OKX](https://www.okx.com/) | CLOB Perp | - |
| `xrpl` | [XRP Ledger](https://xrpl.org/) | CLOB Spot | - |

### Other Connectors

| Connector ID | Exchange | Type | Discount |
|----|------|-------|----------|
| `ascend_ex` | AscendEx | CLOB Spot | - |
| `balancer` | Balancer | AMM | - |
| `bitfinex` | Bitfinex | CLOB Spot | - |
| `bitget_perpetual` | Bitget | CLOB Perp | - |
| `bitmart` | BitMart | CLOB Spot | - |
| `bitrue` | Bitrue | CLOB Spot | - |
| `bitstamp` | Bitstamp | CLOB Spot | - |
| `btc_markets` | BTC Markets | CLOB Spot | - |
| `bybit` | Bybit | CLOB Spot | - |
| `bybit_perpetual` | Bybit | CLOB Perp | - |
| `carbon` | Carbon | AMM | - |
| `coinbase_advanced_trade` | Coinbase | CLOB Spot | - |
| `cube` | Cube | CLOB Spot | - |
| `curve` | Curve | AMM | - |
| `dexalot` | Dexalot | CLOB Spot | - |
| `hashkey` | HashKey | CLOB Spot | - |
| `hashkey_perpetual` | HashKey | CLOB Perp | - |
| `hitbtc` | HitBTC | CLOB Spot | - |
| `injective_v2` | Injective Helix | CLOB Spot | - |
| `injective_v2_perpetual` | Injective Helix | CLOB Perp | - |
| `kraken` | Kraken | CLOB Spot | - |
| `mad_meerkat` | Mad Meerkat | AMM | - |
| `mexc` | MEXC | CLOB Spot | - |
| `ndax` | NDAX | CLOB Spot | - |
| `openocean` | OpenOcean | AMM | - |
| `pancakeswap` | PancakeSwap | AMM | - |
| `pangolin` | Pangolin | AMM | - |
| `polkadex` | Polkadex | CLOB Spot | - |
| `quickswap` | QuickSwap | AMM | - |
| `sushiswap` | SushiSwap | AMM | - |
| `tinyman` | Tinyman | AMM | - |
| `traderjoe` | Trader Joe | AMM | - |
| `uniswap` | Uniswap | AMM | - |
| `vertex` | Vertex | CLOB Spot | - |
| `vvs` | VVS | AMM | - |
| `xsswap` | XSSwap | AMM | - |

## Other Hummingbot Repos

* [Deploy](https://github.com/hummingbot/deploy): Deploy Hummingbot in various configurations with Docker
* [Dashboard](https://github.com/hummingbot/dashboard): Web app that help you create, backtest, deploy, and manage Hummingbot instances
* [Quants Lab](https://github.com/hummingbot/quants-lab): Juypter notebooks that enable you to fetch data and perform research using Hummingbot
* [Gateway](https://github.com/hummingbot/gateway): Typescript based API client for DEX connectors
* [Hummingbot Site](https://github.com/hummingbot/hummingbot-site): Official documentation for Hummingbot - we welcome contributions here too!

## Contributions

The Hummingbot architecture features modular components that can be maintained and extended by individual community members.

We welcome contributions from the community! Please review these [guidelines](./CONTRIBUTING.md) before submitting a pull request.

To have your exchange connector or other pull request merged into the codebase, please submit a New Connector Proposal or Pull Request Proposal, following these [guidelines](https://hummingbot.org/governance/proposals/). Note that you will need some amount of [HBOT tokens](https://etherscan.io/token/0xe5097d9baeafb89f9bcb78c9290d545db5f9e9cb) in your Ethereum wallet to submit a proposal.

## Legal

* **License**: Hummingbot is licensed under [Apache 2.0](./LICENSE).
* **Data collection**: See [Reporting](https://hummingbot.org/reporting/) for information on anonymous data collection and reporting in Hummingbot.

