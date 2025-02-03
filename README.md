![Hummingbot](https://i.ibb.co/X5zNkKw/blacklogo-with-text.png)

----
[![License](https://img.shields.io/badge/License-Apache%202.0-informational.svg)](https://github.com/hummingbot/hummingbot/blob/master/LICENSE)
[![Twitter](https://img.shields.io/twitter/url?url=https://twitter.com/_hummingbot?style=social&label=_hummingbot)](https://twitter.com/_hummingbot)
[![Youtube](https://img.shields.io/youtube/channel/subscribers/UCxzzdEnDRbylLMWmaMjywOA)](https://www.youtube.com/@hummingbot)
[![Discord](https://img.shields.io/discord/530578568154054663?logo=discord&logoColor=white&style=flat-square)](https://discord.gg/hummingbot)

Hummingbot is an open-source framework that helps you design and deploy automated trading strategies, or **bots**, that can run on many centralized or decentralized exchanges. Over the past year, Hummingbot users have generated over $34 billion in trading volume across 140+ unique trading venues. 

The Hummingbot codebase is free and publicly available under the Apache 2.0 open-source license. Our mission is to **democratize high-frequency trading** by creating a global community of algorithmic traders and developers that share knowledge and contribute to the codebase.

## Quick Links

* [Website and Docs](https://hummingbot.org): Official Hummingbot website and documentation
* [Installation](https://hummingbot.org/installation/docker/): Install Hummingbot on various platforms
* [Discord](https://discord.gg/hummingbot): The main gathering spot for the global Hummingbot community
* [YouTube](https://www.youtube.com/c/hummingbot): Videos that teach you how to get the most of of Hummingbot
* [Twitter](https://twitter.com/_hummingbot): Get the latest announcements about Hummingbot
* [Reported Volumes](https://p.datadoghq.com/sb/a96a744f5-a15479d77992ccba0d23aecfd4c87a52): Reported trading volumes across all Hummingbot instances
* [Newsletter](https://hummingbot.substack.com): Get our newsletter whenever we ship a new release


## Exchange Connectors

Hummingbot connectors standardize REST and WebSocket API interfaces to different types of exchanges, enabling you to build sophisticated trading strategies that can be deployed across many exchanges with minimal changes.  We classify exchanges into the following categories:

* **CEX**: Centralized exchanges that take custody of your funds. Use API keys to connect with Hummingbot.
* **DEX**: Decentralized, non-custodial exchanges that operate on a blockchain. Use wallet keys to connect with Hummingbot.

In addition, connectors differ based on the type of market supported:

 * **CLOB Spot**: Connectors to spot markets on central limit order book (CLOB) exchanges
 * **CLOB Perp**: Connectors to perpetual futures markets on CLOB exchanges
 * **AMM**: Connectors to spot markets on Automatic Market Maker (AMM) decentralized exchanges

### Exchange Sponsors

We are grateful for the following exchanges that support the development and maintenance of Hummingbot via broker partnerships and sponsorships.

| Connector ID | Exchange | CEX/DEX | Market Type | Docs | Discount |
|----|------|-------|------|------|----------|
| `binance` | [Binance](https://accounts.binance.com/register?ref=CBWO4LU6) | CEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/binance/) | [![Sign up for Binance using Hummingbot's referral link for a 10% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d10%25&color=orange)](https://accounts.binance.com/register?ref=CBWO4LU6) |
| `binance_perpetual` | [Binance](https://accounts.binance.com/register?ref=CBWO4LU6) | CEX | CLOB Perp | [Docs](https://hummingbot.org/exchanges/binance/) | [![Sign up for Binance using Hummingbot's referral link for a 10% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d10%25&color=orange)](https://accounts.binance.com/register?ref=CBWO4LU6) |
| `gate_io` | [Gate.io](https://www.gate.io/referral/invite/HBOTGATE_0_103) | CEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/gate-io/) | [![Sign up for Gate.io using Hummingbot's referral link for a 10% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d20%25&color=orange)](https://www.gate.io/referral/invite/HBOTGATE_0_103) |
| `gate_io_perpetual` | [Gate.io](https://www.gate.io/referral/invite/HBOTGATE_0_103) | CEX | CLOB Perp | [Docs](https://hummingbot.org/exchanges/gate-io/) | [![Sign up for Gate.io using Hummingbot's referral link for a 20% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d20%25&color=orange)](https://www.gate.io/referral/invite/HBOTGATE_0_103) |
| `htx` | [HTX (Huobi)](https://www.htx.com.pk/invite/en-us/1h?invite_code=re4w9223) | CEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/huobi/) | [![Sign up for HTX using Hummingbot's referral link for a 20% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d20%25&color=orange)](https://www.htx.com.pk/invite/en-us/1h?invite_code=re4w9223) |
| `kucoin` | [KuCoin](https://www.kucoin.com/r/af/hummingbot) | CEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/kucoin/) | [![Sign up for Kucoin using Hummingbot's referral link for a 20% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d20%25&color=orange)](https://www.kucoin.com/r/af/hummingbot) |
| `kucoin_perpetual` | [KuCoin](https://www.kucoin.com/r/af/hummingbot) | CEX | CLOB Perp | [Docs](https://hummingbot.org/exchanges/kucoin/) | [![Sign up for Kucoin using Hummingbot's referral link for a 20% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d20%25&color=orange)](https://www.kucoin.com/r/af/hummingbot) |
| `okx` | [OKX](https://www.okx.com/join/1931920269) | CEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/okx/okx/) | [![Sign up for Kucoin using Hummingbot's referral link for a 20% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d20%25&color=orange)](https://www.okx.com/join/1931920269) |
| `okx_perpetual` | [OKX](https://www.okx.com/join/1931920269) | CEX | CLOB Perp | [Docs](https://hummingbot.org/exchanges/okx/okx/) | [![Sign up for Kucoin using Hummingbot's referral link for a 20% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d20%25&color=orange)](https://www.okx.com/join/1931920269) |
| `dydx_v4_perpetual` | [dYdX](https://www.dydx.exchange/) | DEX | CLOB Perp | [Docs](https://hummingbot.org/exchanges/dydx/) | - |
| `hyperliquid_perpetual` | [Hyperliquid](https://hyperliquid.io/) | DEX | CLOB Perp | [Docs](https://hummingbot.org/exchanges/hyperliquid/) | - |
| `xrpl` | [XRP Ledger](https://xrpl.org/) | DEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/xrpl/) | - |

### Other Exchange Connectors

Currently, the master branch of Hummingbot also includes the following exchange connectors, which are maintained and updated through the Hummingbot Foundation governance process. See [Governance](https://hummingbot.org/governance/) for more information.

| Connector ID | Exchange | CEX/DEX | Type | Docs | Discount |
|----|------|-------|------|------|----------|
| `ascend_ex` | AscendEx | CEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/ascendex/) | - |
| `balancer` | Balancer | DEX | AMM | [Docs](https://hummingbot.org/exchanges/balancer/) | - |
| `bitget_perpetual` | Bitget | CEX | CLOB Perp | [Docs](https://hummingbot.org/exchanges/bitget-perpetual/) | - |
| `bitmart` | BitMart | CEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/bitmart/) | - |
| `bitrue` | Bitrue | CEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/bitrue/) | - |
| `bitstamp` | Bitstamp | CEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/bitstamp/) | - |
| `btc_markets` | BTC Markets | CEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/btc-markets/) | - |
| `bybit` | Bybit | CEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/bybit/) | - |
| `bybit_perpetual` | Bybit | CEX | CLOB Perp | [Docs](https://hummingbot.org/exchanges/bybit/) | - |
| `carbon` | Carbon | DEX | AMM | [Docs](https://hummingbot.org/exchanges/carbon/) | - |
| `coinbase_advanced_trade` | Coinbase | CEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/coinbase/) | - |
| `cube` | Cube | CEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/cube/) | - |
| `curve` | Curve | DEX | AMM | [Docs](https://hummingbot.org/exchanges/curve/) | - |
| `dexalot` | Dexalot | DEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/dexalot/) | - |
| `hashkey` | HashKey | CEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/hashkey/) | - |
| `hashkey_perpetual` | HashKey | CEX | CLOB Perp | [Docs](https://hummingbot.org/exchanges/hashkey/) | - |
| `injective_v2` | Injective Helix | DEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/injective/) | - |
| `injective_v2_perpetual` | Injective Helix | DEX | CLOB Perp | [Docs](https://hummingbot.org/exchanges/injective/) | - |
| `kraken` | Kraken | CEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/kraken/) | - |
| `mad_meerkat` | Mad Meerkat | DEX | AMM | [Docs](https://hummingbot.org/exchanges/mad-meerkat/) | - |
| `mexc` | MEXC | CEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/mexc/) | - |
| `ndax` | NDAX | CEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/ndax/) | - |
| `openocean` | OpenOcean | DEX | AMM | [Docs](https://hummingbot.org/exchanges/openocean/) | - |
| `pancakeswap` | PancakeSwap | DEX | AMM | [Docs](https://hummingbot.org/exchanges/pancakeswap/) | - |
| `pangolin` | Pangolin | CEX | DEX | [Docs](https://hummingbot.org/exchanges/pangolin/) | - |
| `polkadex` | Polkadex | DEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/polkadex/) | - |
| `quickswap` | QuickSwap | DEX | AMM | [Docs](https://hummingbot.org/exchanges/quickswap/) | - |
| `sushiswap` | SushiSwap | DEX | AMM | [Docs](https://hummingbot.org/exchanges/sushiswap/) | - |
| `tinyman` | Tinyman | DEX | AMM | [Docs](https://hummingbot.org/exchanges/tinyman/) | - |
| `traderjoe` | Trader Joe | DEX | AMM | [Docs](https://hummingbot.org/exchanges/traderjoe/) | - |
| `uniswap` | Uniswap | DEX | AMM | [Docs](https://hummingbot.org/exchanges/uniswap/) | - |
| `vertex` | Vertex | DEX | CLOB Spot | [Docs](https://hummingbot.org/exchanges/vertex/) | - |
| `vvs` | VVS | DEX | AMM | [Docs](https://hummingbot.org/exchanges/vvs/) | - |
| `xsswap` | XSSwap | DEX | AMM | [Docs](https://hummingbot.org/exchanges/xswap/) | - |

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

* **License**: Hummingbot is open source and licensed under [Apache 2.0](./LICENSE).
* **Data collection**: See [Reporting](https://hummingbot.org/reporting/) for information on anonymous data collection and reporting in Hummingbot.
