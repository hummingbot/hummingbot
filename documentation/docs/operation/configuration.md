# Configuring Hummingbot

!!! note
    The commands below assume that you are already inside the Hummingbot CLI. Please see our  [installation](/installation) and [client UI](/operation/client) guides if you need help installing and launching the CLI.

We also recommend that users read the [Hummingbot whitepaper](https://www.hummingbot.io/whitepaper.pdf) for more details about trading strategies.

## Getting Started

The `config` command walks you through the process of initializing and configuring the global and strategy-specific settings necessary to run the bot. Running the command will create the following files in the `conf/` folder:

File | Description
---|---
`conf_global.yml` | Global configuration settings, e.g. Binance API keys and Ethereum node.
`conf_arbitrage_strategy_[#].yml` | Settings for the [arbitrage](/strategies/arbitrage/) strategy.
`conf_cross_exchange_market_making_strategy_[#].yml` | Settings for the [cross-exchange market making](/strategies/cross-exchange-market-making/) strategy.
`conf_pure_market_making_strategy_[#].yml` | Settings for the [pure market making](/strategies/pure-market-making/) strategy.
`conf_discovery_strategy_[#].yml` | Settings for the [discovery](/strategies/discovery/) strategy.

!!! tip "Editing Configuration Files Directly"
    Once they are created, you may find it easier to edit the configuration files in the `conf/` folder. Simply open them with a text editor and make any desired modifications.

## Setup Walkthrough

When running `config`, you are asked to select a strategy and enter strategy-specific configuration parameters. We have developed walkthroughs for each strategy:

* [Arbitrage](/strategies/arbitrage#configuration-walkthrough)
* [Cross-exchange market making](/strategies/cross-exchange-market-making#configuration-walkthrough)
* [Pure market making](/strategies/pure-market-making#configuration-walkthrough)
* [Discovery](/strategies/discovery#configuration-walkthrough)

!!! note "Essential Trading Considerations"
    When configuring your bot, make sure you are aware of your exchange's minimum order sizes and fees, and check that your trading pair has sufficient order book and trading volumes. You can find more info about specific exchanges in the [connector section](/connectors).

## Config file templates

This configuration files created and used by Hummingbot are saved in the `conf/` directory of your instance, which you can edit directly with a standard text editor.

The template configuration files can be found here: [Config Templates](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/templates).

!!! warning
    Exit Hummingbot and ensure it is not running when you modify the config files. Changes will take effect the next time Hummingbot is started.
