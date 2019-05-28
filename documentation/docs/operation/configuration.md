# Configuring Hummingbot

!!! note
    The commands below assume that you are already inside the Hummingbot CLI. Please see [Installation](/installation) and [Client](/operation/client) if you need help on installing and launching the CLI.

See the [Hummingbot whitepaper](https://www.hummingbot.io/whitepaper.pdf) for more details about these strategies.

## Getting started

The `config` command walks you through the process of initializing and configuring the global and strategy-specific settings necessary to run the bot, and will create the following files in the `conf/` folder:

File | Description
---|---
`conf_global.yml` | Global configuration settings, e.g. Binance api keys and Ethereum node.
`conf_cross_exchange_market_making_strategy_[#].yml` | Settings for the cross-exchange market making strategy, e.g. token and exchange parameters.
`conf_arbitrage_strategy_[#].yml` | Settings for the arbitrage strategy, e.g. token and exchange parameters.

!!! tip "Tip: Edit Files Directly in `conf/`"
    Once they are created, you may find it easier to edit the configuration files in the `conf/` folder.

## Walkthrough

The `config`, you are asked to select a strategy and enter strategy-specific configuration parameters. We have developed walkthroughs for each strategy:

* [Cross-exchange market making](/strategies/cross-exchange-market-making#configuration-walkthrough)
* [Arbitrage](/strategies/arbitrage#configuration-walkthrough)

## Sample config files

This config files are saved in the `conf/` directory, which you can edit directly.

```yaml+ tab="conf_global.yml"
#################################
###   Global configurations   ###
#################################

# Exchange configs
# Only fill out the credentials for the markets you are trading on
binance_api_key: null
binance_api_secret: null

# Ethereum wallet address: required for trading on a DEX
wallet: null
ethereum_rpc_url: null

# Advanced configs: Do NOT touch unless you understand what you are changing
client_id: null
log_level: INFO
debug_console: false
strategy_report_interval: 900.0
reporting_aggregation_interval: 60.0
reporting_log_interval: 60.0
logger_override_whitelist:
- hummingbot.strategy
- hummingbot.market
- hummingbot.wallet
- conf
key_file_path: conf/
log_file_path: logs/
on_chain_cancel_on_exit: false

# For more detailed information: https://docs.hummingbot.io
```

```yaml+ tab="conf_cross_exchange_market_making_strategy.yml"
########################################################
###   Cross exchange market making strategy config   ###
########################################################

# The following configuations are only required for the
# cross exchange market making strategy

# Exchange and token parameters
maker_market: null
taker_market: null
maker_market_symbol: null
taker_market_symbol: null

# Minimum profitability target required to place an order
# Expressed in decimals: 0.01 = 1% target profit
min_profitability: null

# Maximum order size in terms of quote currency
trade_size_override: null

# Maximum aggregate amount of orders in quote currency
# that are allowed at a better price than Hummingbot's
# order before Hummingbot adjusts its order and pricing
top_depth_tolerance: null

# Have Hummingbot actively adjust/cancel orders if necessary.
# If set to true, outstanding orders are adjusted if
# profitability falls below min_profitability.
# If set to false, outstanding orders are adjusted if
# profitability falls below cancel_order_threshold.
active_order_canceling: null

# If active_order_canceling = false, this is the profitability/
# loss threshold at which to cancel the order.
# Expressed in decimals: 0.01 = 1% target profit
cancel_order_threshold: null

# An amount in seconds, which is the minimum duration for any
# placed limit orders. Default value = 130 seconds.
limit_order_min_expiration: null

# For more detailed information, see:
# https://docs.hummingbot.io/configuration/#hummingbot-configuration-variables
```

```yaml+ tab="conf_arbitrage_strategy.yml"
#####################################
###   Arbitrage strategy config   ###
#####################################

# The following configuations are only required for the
# arbitrage strategy

# Exchange and token parameters
primary_market: null
secondary_market: null
primary_market_symbol: null
secondary_market_symbol: null

# Minimum profitability target required to place an order
# Expressed in decimals: 0.01 = 1% target profit
min_profitability: null

# For more detailed information, see:
# https://docs.hummingbot.io/configuration/#hummingbot-configuration-variables
```


!!! warning
    Exit Hummingbot and ensure it is not running when you modify the config files.  Changes will take effect the next time Hummingbot is started.
