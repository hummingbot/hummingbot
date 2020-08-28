# Configuring Hummingbot

!!! note
    The commands below assume that you are already inside the Hummingbot CLI. Please see our  [installation](/installation) and [client UI](/operation/client) guides if you need help installing and launching the CLI.

## Getting Started

The `create` command walks you through the process of initializing and configuring the global and strategy-specific settings necessary to run the bot. Running the command will create the following files in the `conf/` folder:

File | Description
---|---
`conf_global.yml` | Global configuration settings, e.g. Binance API keys and Ethereum node.
`conf_arb_[#].yml` | Settings for the [arbitrage](/strategies/arbitrage/) strategy.
`conf_xemm_[#].yml` | Settings for the [cross-exchange market making](/strategies/cross-exchange-market-making/) strategy.
`conf_pure_mm_[#].yml` | Settings for the [pure market making](/strategies/pure-market-making/) strategy.

!!! tip "Editing Configuration Files Directly"
    Once they are created, you may find it easier to edit the configuration files in the `conf/` folder. Simply open them with a text editor and make any desired modifications.

## Setup Walkthrough

When running `create`, you are asked to select a strategy and enter strategy-specific configuration parameters. We have developed walkthroughs for each strategy:

* [Arbitrage](/strategies/arbitrage#configuration-walkthrough)
* [Cross-exchange market making](/strategies/cross-exchange-market-making#configuration-walkthrough)
* [Pure market making](/strategies/pure-market-making#configuration-walkthrough)

!!! note "Essential Trading Considerations"
    When configuring your bot, make sure you are aware of your exchange's minimum order sizes and fees, and check that your trading pair has sufficient order book and trading volumes. You can find more info about specific exchanges in the [Connectors](/connectors) section.

# API keys

In order to trade on a centralized exchange, you will need to import your API key from that exchange to Hummingbot using the `connect [exchange_name]` command. API keys are account specific credentials that allow access to live information and trading outside of the exchange website.

Please see below for instructions to find your API keys for the exchanges that Hummingbot currently supports:

* [Binance](/connectors/binance/#creating-binance-api-keys)

* [Coinbase Pro](/connectors/coinbase/#creating-coinbase-pro-api-keys)

* [Huobi Global](/connectors/huobi/#creating-huobi-api-keys)

* [Bittrex Global](/connectors/bittrex/#creating-bittrex-api-keys)

* [Liquid](/connectors/liquid/#creating-liquid-api-keys)

* [KuCoin](/connectors/kucoin/#creating-kucoin-api-keys)

* [Kraken](/connectors/kraken/#creating-kraken-api-keys)

* [Eterbase](/connectors/eterbase/#creating-eterbase-api-keys)

!!! warning "API key permissions"
    We recommend using only **"trade"** enabled API keys; enabling **"withdraw", "transfer", or the equivalent** is unnecessary for current Hummingbot strategies.

## Config file templates

This configuration files created and used by Hummingbot are saved in the `conf/` directory of your instance, which you can edit directly with a standard text editor.

The template configuration files can be found here: [Config Templates](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/templates).

!!! warning
    Exit Hummingbot and ensure it is not running when you modify the config files. Changes will take effect the next time Hummingbot is started.
