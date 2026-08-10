# Kairos-2

[![License](https://img.shields.io/badge/License-Apache%202.0-informational.svg)](./LICENSE)

**Kairos-2** is a market making trading client for **Binance**. It is a stripped-down fork of
[Hummingbot](https://github.com/hummingbot/hummingbot), reduced to a single exchange and a single
class of strategy so there is far less surface to read, build, and reason about.

## What's in this fork

**Exchanges — Binance only**

| Connector | Type | ID |
|---|---|---|
| Binance | Spot | `binance` |
| Binance | Perpetual futures | `binance_perpetual` |
| Binance | Paper trading (simulated) | `binance_paper_trade` |

**Strategies — market making only**

* **[V2 controllers](./controllers/market_making)** — the modern framework: `pmm_simple`,
  `pmm_dynamic`, `dman_maker_v2`, plus [`pmm_v1`](./controllers/generic/pmm_v1.py). Configs can be
  backtested and tuned live while the bot runs.
* **[V1 `pure_market_making`](./kairos/strategy/pure_market_making)** — the classic PMM strategy.
* **[V1 `avellaneda_market_making`](./kairos/strategy/avellaneda_market_making)** — market making
  with the Avellaneda–Stoikov model (spreads driven by inventory and volatility).
* **[Scripts](./scripts)** — single-file Python strategies, e.g.
  [`simple_pmm.py`](./scripts/simple_pmm.py).

**Executors** still available to controllers: position, DCA, grid, order, and TWAP.

### What was removed

Relative to upstream Hummingbot: all non-Binance connectors (25 spot exchanges, 18 perpetual
venues), the Gateway/DEX layer and every AMM/CLOB-DEX integration, and all non-market-making
strategies (arbitrage, XEMM, hedge, liquidity mining, directional trading, grid/LP controllers).
Candles feeds and rate-oracle sources were narrowed to Binance, CoinGecko, and CoinCap.

## Getting started

Requires [Anaconda or Miniconda](https://www.anaconda.com/download).

```bash
git clone https://github.com/Acaua-Rangel/Kairos-2.git
cd Kairos-2

make install            # create the conda env, build the Cython extensions, expose `hbot`
conda activate kairos-2
hbot --help
```

The CLI command is still named `hbot`, and so are the exchange order-id prefixes — see
[Naming](#naming) below.

### Paper trading first

`binance_paper_trade` simulates fills against live Binance market data, so no API keys are needed:

```bash
hbot create simple_pmm --name conf_paper_bot.yml \
     --set exchange=binance_paper_trade --set trading_pair=BTC-USDT
hbot start conf_paper_bot.yml
hbot status
hbot stop
```

### Live trading

```bash
hbot connect binance                                   # store API keys (encrypted at rest)
hbot create pmm_simple --name conf_my_bot.yml \
     --set connector_name=binance --set trading_pair=BTC-USDT --set total_amount_quote=100
hbot start conf_my_bot.yml
```

On first use `hbot` prompts for a keystore password that encrypts your API keys. Set
`HBOT_PASSWORD` or pass `--password-stdin` to run non-interactively.

Full command reference: **[hbot CLI guide](kairos/cli/README.md)**.

### Docker

```bash
git clone https://github.com/Acaua-Rangel/Kairos-2.git
cd Kairos-2
make setup
make deploy           # start the container
make link-cli         # put `hbot` on the host PATH (dispatches into the container)
```

Or use the interactive full-screen client with `docker attach kairos-2`.

## Naming

The Python package is `kairos`; the distribution is `kairos-2`; the conda environment and Docker
image are `kairos-2`. Two upstream names were deliberately **kept**:

* **`hbot`** — the CLI command name, so muscle memory and existing scripts keep working.
* **`hbot` order-id prefixes** (`kairos/connector/utils.py`) — these are part of Binance's broker
  program. Changing them would silently alter how orders are attributed, so they are untouched.

## Legal

Kairos-2 is a fork of Hummingbot and remains licensed under [Apache 2.0](./LICENSE). The original
copyright of the Hummingbot Foundation is retained in `LICENSE` as that license requires.

Anonymous usage metrics inherited from upstream still report a `hummingbot-client` source string
and can be disabled via `anonymized_metrics_mode` in the client config.
