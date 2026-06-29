![Hummingbot](https://github.com/user-attachments/assets/3213d7f8-414b-4df8-8c1b-a0cd142a82d8)

----
[![License](https://img.shields.io/badge/License-Apache%202.0-informational.svg)](https://github.com/hummingbot/hummingbot/blob/master/LICENSE)
[![Twitter](https://img.shields.io/twitter/url?url=https://twitter.com/_hummingbot?style=social&label=_hummingbot)](https://twitter.com/_hummingbot)
[![Youtube](https://img.shields.io/youtube/channel/subscribers/UCxzzdEnDRbylLMWmaMjywOA)](https://www.youtube.com/@hummingbot)
[![Discord](https://img.shields.io/discord/530578568154054663?logo=discord&logoColor=white&style=flat-square)](https://discord.gg/hummingbot)

Hummingbot is an open-source framework that helps you design and deploy automated trading strategies, or **bots**, that can run on many centralized or decentralized exchanges. Over the past year, Hummingbot users have generated over $34 billion in trading volume across 140+ unique trading venues.

The Hummingbot codebase is free and publicly available under the Apache 2.0 open-source license. Our mission is to **democratize high-frequency trading** by creating a global community of algorithmic traders and developers that share knowledge and contribute to the codebase.

## Quick Links

* [Website and Docs](https://hummingbot.org): Official Hummingbot website and documentation
* [Installation](https://hummingbot.org/installation/): Install Hummingbot on various platforms
* [Discord](https://discord.gg/hummingbot): The main gathering spot for the global Hummingbot community
* [YouTube](https://www.youtube.com/c/hummingbot): Videos that teach you how to get the most out of Hummingbot
* [Spotify Podcast - The Bot Pod](https://open.spotify.com/show/1muzSO0SZqYBVQu2DXzGB1?si=ae9a9c0674c64b45): Weekly livestream and podcast by Hummingbot maintainers
* [Twitter](https://twitter.com/_hummingbot): Get the latest announcements about Hummingbot
* [Reported Volumes](https://reporting.hummingbot.org/): Reported trading volumes across all Hummingbot instances
* [Newsletter](https://hummingbot.substack.com): Get our newsletter whenever we ship a new release

## Getting Started

The recommended way to run Hummingbot is the **`hbot` command-line interface**, installed from
source. `hbot` runs, controls, and monitors a trading bot non-interactively: start/stop a bot, author
and tune configs, and read trades, PnL, logs, and status — all scriptable, with `--json` output and
stable exit codes. See the **[hbot CLI guide](hummingbot/cli/README.md)** for the full reference.

### Install and run with `hbot` (recommended)

Requires [Anaconda or Miniconda](https://www.anaconda.com/download).

```bash
# Clone the repository
git clone https://github.com/hummingbot/hummingbot.git
cd hummingbot

# Create the conda environment, build extensions, and expose the `hbot` CLI
make install

# Activate the environment
conda activate hummingbot
hbot --help
```

Then connect an exchange, create a config, and start a bot:

```bash
hbot connect binance                                   # store API keys (encrypted)
hbot strategy create pmm_simple --name conf_my_bot.yml \
     --set connector_name=binance --set trading_pair=BTC-USDT --set total_amount_quote=100
hbot start conf_my_bot.yml                             # run it (one bot per install)
hbot status                                            # check on it
hbot stop                                              # stop gracefully
```

For on-chain (DEX) trading, `hbot gateway` manages the Gateway service:

```bash
hbot gateway start          # launch Gateway (DEX middleware)
hbot gateway connect solana # add a wallet
```

Full command reference and ontology: **[hbot CLI guide](hummingbot/cli/README.md)**.

---

### Other ways to run Hummingbot

**Docker (interactive client).** Run the traditional interactive Hummingbot client in a container — install [Docker Compose](https://docs.docker.com/compose/install/), then:

```bash
git clone https://github.com/hummingbot/hummingbot.git
cd hummingbot
make setup            # answer `y` to "Include Gateway?" to add the DEX middleware
make deploy
docker attach hummingbot
```

With Gateway included, it starts in development mode (unencrypted HTTP). For production HTTPS, use the `DEV=false` flag and run `gateway generate-certs`. See [Development vs Production Modes](https://hummingbot.org/gateway/installation/#development-vs-production-modes).

**Interactive client from source.** Run the interactive client directly from a source install:

```bash
make install
make run
```

**[Condor](https://github.com/hummingbot/condor) (Telegram bot).** Follow the instructions in the [Condor docs](https://hummingbot.org/condor/).

---

For comprehensive installation instructions and troubleshooting, visit our [Installation](https://hummingbot.org/installation/) documentation.

## Getting Help

If you encounter issues or have questions, here's how you can get assistance:

* Consult our [FAQ](https://hummingbot.org/faq/), [Troubleshooting Guide](https://hummingbot.org/troubleshooting/), or [Glossary](https://hummingbot.org/glossary/)
* To report bugs or suggest features, submit a [GitHub issue](https://github.com/hummingbot/hummingbot/issues)
* Join our [Discord community](https://discord.gg/hummingbot) and ask questions in the #support channel

We pledge that we will not use the information/data you provide us for trading purposes nor share them with third parties.

## Exchange Connectors

Hummingbot connectors standardize REST and WebSocket API interfaces to different types of exchanges, enabling you to build sophisticated trading strategies that can be deployed across many exchanges with minimal changes.

### Connector Types

We classify exchange connectors into three main categories:

* **CLOB CEX**: Centralized exchanges with central limit order books that take custody of your funds. Connect via API keys.
  - **Spot**: Trading spot markets
  - **Perpetual**: Trading perpetual futures markets

* **CLOB DEX**: Decentralized exchanges with on-chain central limit order books. Non-custodial, connect via wallet keys.
  - **Spot**: Trading spot markets on-chain
  - **Perpetual**: Trading perpetual futures on-chain

* **AMM DEX**: Decentralized exchanges using Automated Market Maker protocols. Non-custodial, connect via Gateway middleware.
  - **Router**: DEX aggregators that find optimal swap routes
  - **AMM**: Traditional constant product (x*y=k) pools
  - **CLMM**: Concentrated Liquidity Market Maker pools with custom price ranges

### Exchange Sponsors

We are grateful for the following exchanges that support the development and maintenance of Hummingbot via broker partnerships and sponsorships.

| Exchange | Type | Sub-Type(s) | Connector ID(s) | Discount |
|------|------|------|-------|----------|
| [Binance](https://hummingbot.org/exchanges/binance/) | CLOB CEX | Spot, Perpetual | `binance`, `binance_perpetual` | [![Sign up for Binance using Hummingbot's referral link for a 10% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d10%25&color=orange)](https://accounts.binance.com/register?ref=CBWO4LU6) |
| [BitMart](https://hummingbot.org/exchanges/bitmart/) | CLOB CEX | Spot, Perpetual | `bitmart`, `bitmart_perpetual` | [![Sign up for BitMart using Hummingbot's referral link!](https://img.shields.io/static/v1?label=Sponsor&message=Link&color=orange)](https://www.bitmart.com/invite/Hummingbot/en) |
| [Bitget](https://hummingbot.org/exchanges/bitget/) | CLOB CEX | Spot, Perpetual | `bitget`, `bitget_perpetual` | [![Sign up for Bitget using Hummingbot's referral link!](https://img.shields.io/static/v1?label=Sponsor&message=Link&color=orange)](https://www.bitget.com/expressly?channelCode=v9cb&vipCode=26rr&languageType=0) |
| [Derive](https://hummingbot.org/exchanges/derive/) | CLOB DEX | Spot, Perpetual | `derive`, `derive_perpetual` | [![Sign up for Derive using Hummingbot's referral link!](https://img.shields.io/static/v1?label=Sponsor&message=Link&color=orange)](https://www.derive.xyz/invite/7SA0V) |
| [dYdX](https://hummingbot.org/exchanges/dydx/) | CLOB DEX | Perpetual | `dydx_v4_perpetual` | - |
| [Gate.io](https://hummingbot.org/exchanges/gate-io/) | CLOB CEX | Spot, Perpetual | `gate_io`, `gate_io_perpetual` | [![Sign up for Gate.io using Hummingbot's referral link for a 20% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d20%25&color=orange)](https://www.gate.io/referral/invite/HBOTGATE_0_103) |
| [HTX (Huobi)](https://hummingbot.org/exchanges/htx/) | CLOB CEX | Spot | `htx` | [![Sign up for HTX using Hummingbot's referral link for a 20% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d20%25&color=orange)](https://www.htx.com.pk/invite/en-us/1h?invite_code=re4w9223) |
| [Hyperliquid](https://hummingbot.org/exchanges/hyperliquid/) | CLOB DEX | Spot, Perpetual | `hyperliquid`, `hyperliquid_perpetual` | - |
| [KuCoin](https://hummingbot.org/exchanges/kucoin/) | CLOB CEX | Spot, Perpetual | `kucoin`, `kucoin_perpetual` | [![Sign up for Kucoin using Hummingbot's referral link for a 20% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d20%25&color=orange)](https://www.kucoin.com/r/af/hummingbot) |
| [OKX](https://hummingbot.org/exchanges/okx/) | CLOB CEX | Spot, Perpetual | `okx`, `okx_perpetual` | [![Sign up for OKX using Hummingbot's referral link for a 20% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d20%25&color=orange)](https://www.okx.com/join/1931920269) |
| [XRP Ledger](https://hummingbot.org/exchanges/xrpl/) | CLOB DEX | Spot | `xrpl` | - |

### Other Exchange Connectors

Currently, the master branch of Hummingbot also includes the following exchange connectors, which are maintained and updated through the Hummingbot Foundation governance process. See [Governance](https://hummingbot.org/governance/) for more information.

| Exchange | Type | Sub-Type(s) | Connector ID(s) | Discount |
|------|------|------|-------|----------|
| [0x Protocol](https://hummingbot.org/exchanges/gateway/0x/) | AMM DEX | Router | `0x` | - |
| [Aevo](https://hummingbot.org/exchanges/aevo/) | CLOB CEX | Perpetual | `aevo_perpetual` | - |
| [Architect](https://hummingbot.org/exchanges/architect/) | CLOB CEX | Perpetual | `architect_perpetual` | - |
| [AscendEx](https://hummingbot.org/exchanges/ascendex/) | CLOB CEX | Spot | `ascend_ex` | - |
| [Backpack](https://hummingbot.org/exchanges/backpack/) | CLOB CEX | Spot, Perpetual | `backpack`, `backpack_perpetual` | - |
| [Balancer](https://hummingbot.org/exchanges/gateway/balancer/) | AMM DEX | AMM | `balancer` | - |
| [BingX](https://hummingbot.org/exchanges/bing_x/) | CLOB CEX | Spot | `bing_x` | - |
| [Bitrue](https://hummingbot.org/exchanges/bitrue/) | CLOB CEX | Spot | `bitrue` | - |
| [Bitstamp](https://hummingbot.org/exchanges/bitstamp/) | CLOB CEX | Spot | `bitstamp` | - |
| [BTC Markets](https://hummingbot.org/exchanges/btc-markets/) | CLOB CEX | Spot | `btc_markets` | - |
| [Bybit](https://hummingbot.org/exchanges/bybit/) | CLOB CEX | Spot, Perpetual | `bybit`, `bybit_perpetual` | - |
| [Coinbase](https://hummingbot.org/exchanges/coinbase/) | CLOB CEX | Spot | `coinbase_advanced_trade` | - |
| [Cube](https://hummingbot.org/exchanges/cube/) | CLOB CEX | Spot | `cube` | - |
| [Curve](https://hummingbot.org/exchanges/gateway/curve/) | AMM DEX | AMM | `curve` | - |
| [Decibel](https://hummingbot.org/exchanges/decibel/) | CLOB CEX | Perpetual | `decibel_perpetual` | - |
| [Dexalot](https://hummingbot.org/exchanges/dexalot/) | CLOB DEX | Spot | `dexalot` | - |
| [EVEDEX](https://hummingbot.org/exchanges/evedex/) | CLOB CEX | Perpetual | `evedex_perpetual` | - |
| [Foxbit](https://hummingbot.org/exchanges/foxbit/) | CLOB CEX | Spot | `foxbit` | - |
| [GRVT](https://hummingbot.org/exchanges/grvt/) | CLOB CEX | Perpetual | `grvt_perpetual` | - |
| [Injective Helix](https://hummingbot.org/exchanges/injective/) | CLOB DEX | Spot, Perpetual | `injective_v2`, `injective_v2_perpetual` | - |
| [Jupiter](https://hummingbot.org/exchanges/gateway/jupiter/) | AMM DEX | Router | `jupiter` | - |
| [Kraken](https://hummingbot.org/exchanges/kraken/) | CLOB CEX | Spot | `kraken` | - |
| [Meteora](https://hummingbot.org/exchanges/gateway/meteora/) | AMM DEX | CLMM | `meteora` | - |
| [MEXC](https://hummingbot.org/exchanges/mexc/) | CLOB CEX | Spot | `mexc` | - |
| [NDAX](https://hummingbot.org/exchanges/ndax/) | CLOB CEX | Spot | `ndax` | - |
| [Pacifica](https://hummingbot.org/exchanges/pacifica/) | CLOB CEX | Perpetual | `pacifica_perpetual` | - |
| [PancakeSwap](https://hummingbot.org/exchanges/gateway/pancakeswap/) | AMM DEX | AMM | `pancakeswap` | - |
| [QuickSwap](https://hummingbot.org/exchanges/gateway/quickswap/) | AMM DEX | AMM | `quickswap` | - |
| [Raydium](https://hummingbot.org/exchanges/gateway/raydium/) | AMM DEX | AMM, CLMM | `raydium` | - |
| [SushiSwap](https://hummingbot.org/exchanges/gateway/sushiswap/) | AMM DEX | AMM | `sushiswap` | - |
| [Trader Joe](https://hummingbot.org/exchanges/gateway/traderjoe/) | AMM DEX | AMM | `traderjoe` | - |
| [Uniswap](https://hummingbot.org/exchanges/gateway/uniswap/) | AMM DEX | Router, AMM, CLMM | `uniswap` | - |
| [Vertex](https://hummingbot.org/exchanges/vertex/) | CLOB DEX | Spot | `vertex` | - |

## Other Hummingbot Repos

* [Condor](https://github.com/hummingbot/condor): Telegram Interface for Hummingbot
* [Hummingbot API](https://github.com/hummingbot/hummingbot-api): The central hub for running Hummingbot trading bots
* [Hummingbot MCP](https://github.com/hummingbot/mcp): Enables AI assistants like Claude and Gemini to interact with Hummingbot for automated cryptocurrency trading across multiple exchanges.
* [Quants Lab](https://github.com/hummingbot/quants-lab): Jupyter notebooks that enable you to fetch data and perform research using Hummingbot
* [Gateway](https://github.com/hummingbot/gateway): Typescript based API client for DEX connectors
* [Hummingbot Site](https://github.com/hummingbot/hummingbot-site): Official documentation for Hummingbot - we welcome contributions here too!

## Contributions

The Hummingbot architecture features modular components that can be maintained and extended by individual community members.

We welcome contributions from the community! Please review these [guidelines](./CONTRIBUTING.md) before submitting a pull request.

To have your exchange connector or other pull request merged into the codebase, please submit a New Connector Proposal or Pull Request Proposal, following these [guidelines](https://hummingbot.org/about/proposals/). Note that you will need some amount of [HBOT tokens](https://etherscan.io/token/0xe5097d9baeafb89f9bcb78c9290d545db5f9e9cb) in your Ethereum wallet to submit a proposal.

## Legal

* **License**: Hummingbot is open source and licensed under [Apache 2.0](./LICENSE).
* **Data collection**: See [Reporting](https://hummingbot.org/reporting/) for information on anonymous data collection and reporting in Hummingbot.
