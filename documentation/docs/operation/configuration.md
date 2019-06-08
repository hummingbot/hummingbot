# Configuring Hummingbot

!!! note
    The commands below assume that you are already inside the Hummingbot CLI. Please see [Installation](/installation) and [Client](/operation/client) if you need help on installing and launching the CLI.

See the [Hummingbot whitepaper](https://www.hummingbot.io/whitepaper.pdf) for more details about these strategies.

## Getting started

The `config` command walks you through the process of initializing and configuring the global and strategy-specific settings necessary to run the bot, and will create the following files in the `conf/` folder:

File | Description
---|---
`conf_global.yml` | Global configuration settings, e.g. Binance api keys and Ethereum node.
`conf_cross_exchange_market_making_strategy_[#].yml` | Settings for the cross-exchange market making strategy.
`conf_arbitrage_strategy_[#].yml` | Settings for the [arbitrage](/strategies/arbitrage/) strategy.
`conf_pure_market_making_[#].yml` | Settings for the [pure market making](/strategies/pure-market-making/) strategy.
`conf_discovery_strategy_[#].yml` | Settings for the [discovery](/strategies/discovery/) strategy.

!!! tip "Tip: Edit Files Directly in `conf/`"
    Once they are created, you may find it easier to edit the configuration files in the `conf/` folder.

## Walkthrough

The `config`, you are asked to select a strategy and enter strategy-specific configuration parameters. We have developed walkthroughs for each strategy:

* [Cross-exchange market making](/strategies/cross-exchange-market-making#configuration-walkthrough)
* [Arbitrage](/strategies/arbitrage#configuration-walkthrough)

## Config file templates

This config files created and used by `hummingbot` are saved in the `conf/` directory, which you can edit directly.

The template configuration files can be found here: [config templates](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/templates).

!!! warning
    Exit Hummingbot and ensure it is not running when you modify the config files.  Changes will take effect the next time Hummingbot is started.
