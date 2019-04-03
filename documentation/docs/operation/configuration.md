# Configuring Hummingbot

!!! note
    The commands below assume that you are already inside the Hummingbot CLI. Please see [Installation](/installation) and [Client](/client) if you need help on installing and launching the CLI.

Hummingbot currently has two strategies: (1) [cross-exchange market making](/configuration/#cross-exchange-market-making), and (2) [arbitrage](/configuration/#arbitrage).
See the [Hummingbot whitepaper](https://www.hummingbot.io/whitepaper.pdf) for more details about these strategies.

### Initializing with `config`

The `config` command walks you through the process of initializing and configuring the global and strategy-specific settings necessary to run the bot, and will create the following files in the `conf/` folder:

File | Description
---|---
`conf_global.yml` | Global configuration settings, e.g. Binance api keys and Ethereum node.
`conf_cross_exchange_market_making_strategy_[#].yml` | Settings for the cross-exchange market making strategy, e.g. token and exchange parameters.
`conf_arbitrage_strategy_[#].yml` | Settings for the arbitrage strategy, e.g. token and exchange parameters.

!!! tip "Tip: Edit Files Directly in `conf/`"
    Once they are created, you may find it easier to edit the configuration files in the `conf/` folder.

## Cross exchange market making

### Prerequisites: Inventory

1. For cross-exchange market making, you will need to hold inventory on two exchanges, one where the bot will make a market (the **maker exchange**) and another where the bot will source liquidity and hedge any filled orders (the **taker exchange**).
2. You will also need some Ethereum to pay gas for transactions on a DEX (if applicable).

Initially, we assume that the maker exchange is an Ethereum-based decentralized exchange and that the taker exchange is Binance.

### Walkthrough `config`

The following walks through all the steps when running `config` for the first time.

!!! tip "Tip: Automcomplete Inputs during Configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.

| Prompt | Description |
|-----|-----|
| `What is your market making strategy >>>`: | Enter `cross_exchange_market_making`.<br/><br/>Currently available options: `cross_exchange_market_making` or `arbitrage` *(case sensitive)* |
| `Import previous configs or create a new config file? (import/create) >>>`: | When running the bot for the first time, enter `create`.<br/>If you have previously initialized, enter `import`, which will then ask you to specify the config file location. |
| `Enter your maker exchange name >>>`: | In the cross-exchange market making strategy, the *maker exchange* is the exchange where the bot will place maker orders.<br/><br/>Currently available options: `radar_relay` or `ddex` *(case sensitive)* |
| `Enter your taker exchange name >>>`: | In the cross-exchange market making strategy, the *taker exchange* is the exchange where the bot will place taker orders.<br/><br/>Currently available option: `binance` *(case sensitive)*|
| `Enter the token symbol you would like to trade on [maker exchange name] >>>`: | Enter the token symbol for the *maker exchange*.<br/>Example input: `ZRX-WETH`<br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: ensure that the pair is a valid pair for the exchange, for example, use `WETH` instead of `ETH`.</td></tr></tbody></table> |
| `Enter the token symbol you would like to trade on [taker exchange name] >>>`: | Enter the token symbol for the *taker exchange*.<br/>Example input: `ZRX-ETH`<br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: ensure that (1) the pair corresponds with the token symbol entered for the maker exchange, and that (2) is a valid pair for the exchange.  *Note in the example, the use of `ETH` instead of `WETH`*.</td></tr></tbody></table>|
| `What is the minimum profitability for your to make a trade? (Enter 0.01 to indicate 1%) >>>`: | This sets `min_profitability` (see [definition](/configuration/#hummingbot-configuration-variables)). |
| `Do you want to actively adjust/cancel orders (Default True) >>>`: | This sets `active_order_canceling` (see [definition](/configuration/#cross-exchange-market-making-only)). |
| `What is the minimum profitability to actively cancel orders? (Default to 0.0, only specify when active_order_cancelling is disabled, value can be negative) >>>`: | This sets the `cancel_order_threshold` (see [definition](/configuration/#cross-exchange-market-making-only)). |
| `What is the minimum limit order expiration in seconds? (Default to 130 seconds) >>>`: | This sets the `limit_order_min_expiration` (see [definition](/configuration/#cross-exchange-market-making-only)). |
| `Enter your Binance API key >>>`:<br/><br/>`Enter your Binance API secret >>>`: | You must [create a Binance API key](https://support.binance.com/hc/en-us/articles/360002502072-How-to-create-API) key with trading enabled ("Enable Trading" selected).<br/><table><tbody><tr><td bgcolor="#e5f8f6">**Tip**: You can use Ctrl + R or ⌘ + V to paste from the clipboard.</td></tr></tbody></table> |
| `Would you like to import an existing wallet or create a new wallet? (import / create) >>>`: | Import or create an Ethereum wallet which will be used for trading on DDEX.<br/><br/>Enter a valid input:<ol><li>`import`: imports a wallet from an input private key.</li><ul><li>If you select import, you will then be asked to enter your private key as well as a password to lock/unlock that wallet for use with Hummingbot</li><li>`Your wallet private key >>>`</li><li>`A password to protect your wallet key >>>`</li></ul><li>`create`: creates a new wallet with new private key.</li><ul><li>If you select create, you will only be asked for a password to protect your newly created wallet</li><li>`A password to protect your wallet key >>>`</li></ul></ol><br/><table><tbody><tr><td bgcolor="#e5f8f6">**Tip**: using a wallet that is available in your Metamask (i.e. importing a wallet from Metamask) allows you to view orders created and trades filled by Hummingbot on the decentralized exchange's website.</td></tr></tbody></table> |
| `Which Ethereum node would you like your client to connect to? (default hummingbot public node) >>>`: | Enter an Ethereum node for Hummingbot to use.  For example, if you are running a local Ethereum client, the standard connection URL would be `http://localhost:8545`.<table><tbody><tr><td bgcolor="#ecf3ff">**Note**: for the alpha program, CoinAlpha is making available a node for use.  Leave input blank to default to the temporarily provided node.</td></tr></tbody></table> |

---

## Arbitrage

### Prerequisites: Inventory

1. Similar to cross-exchange market making, you will need to hold inventory on two exchanges (a **primary** and **secondary** exchange), in order to be able to trade and capture price differentials (i.e. buy low on one exchange, sell high on the other).
2. You will also need some Ethereum to pay gas for transactions on a DEX (if applicable).

### Walkthrough `config`

The following walks through all the steps when running `config` for the first time.

!!! tip "Tip: Automcomplete Inputs during Configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.

| Prompt | Description |
|-----|-----|
| `What is your market making strategy >>>`: | Enter `arbitrage`.<br/><br/>Currently available options: `cross_exchange_market_making` or `arbitrage` *(case sensitive)* |
| `Import previous configs or create a new config file? (import/create) >>>`: | When running the bot for the first time, enter `create`.<br/>If you have previously initialized, enter `import`, which will then ask you to specify the config file location. |
| `Enter your primary exchange name >>>`: | Enter an exchange you would like to trade on.<br/><br/>Currently available options: `binance`, `radar_relay` or `ddex` *(case sensitive)* |
| `Enter your secondary exchange name >>>`: | Enter another exchange you would like to trade on.<br/><br/>Currently available options: `binance`, `radar_relay` or `ddex` *(case sensitive)* |
| `Enter the token symbol you would like to trade on [primary exchange name] >>>`: | Enter the token symbol for the *primary exchange*. |
| `Enter the token symbol you would like to trade on [secondary exchange name] >>>`: | Enter the token symbol for the *secondary exchange*. |
| `What is the minimum profitability for your to make a trade? (Enter 0.01 to indicate 1%) >>>`: | This sets `min_profitability` (see [definition](/configuration/#hummingbot-configuration-variables)). |
| `Enter your Binance API key >>>`:<br/><br/>`Enter your Binance API secret >>>`: | You must [create a Binance API key](https://support.binance.com/hc/en-us/articles/360002502072-How-to-create-API) key with trading enabled ("Enable Trading" selected).<br/><table><tbody><tr><td bgcolor="#e5f8f6">**Tip**: You can use Ctrl + R or ⌘ + V to paste from the clipboard.</td></tr></tbody></table> |
| `Would you like to import an existing wallet or create a new wallet? (import / create) >>>`: | Import or create an Ethereum wallet which will be used for trading on DDEX.<br/><br/>Enter a valid input:<ol><li>`import`: imports a wallet from an input private key.</li><ul><li>If you select import, you will then be asked to enter your private key as well as a password to lock/unlock that wallet for use with Hummingbot</li><li>`Your wallet private key >>>`</li><li>`A password to protect your wallet key >>>`</li></ul><li>`create`: creates a new wallet with new private key.</li><ul><li>If you select create, you will only be asked for a password to protect your newly created wallet</li><li>`A password to protect your wallet key >>>`</li></ul></ol><br/><table><tbody><tr><td bgcolor="#e5f8f6">**Tip**: using a wallet that is available in your Metamask (i.e. importing a wallet from Metamask) allows you to view orders created and trades filled by Hummingbot on the decentralized exchange's website.</td></tr></tbody></table> |
| `Which Ethereum node would you like your client to connect to? (default hummingbot public node) >>>`: | Enter an Ethereum node for Hummingbot to use.  For example, if you are running a local Ethereum client, the standard connection URL would be `http://localhost:8545`.<table><tbody><tr><td bgcolor="#ecf3ff">**Note**: for the alpha program, CoinAlpha is making available a node for use.  Leave input blank to default to the temporarily provided node.</td></tr></tbody></table> |

---

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
- hummingbot.strategy.arbitrage
- hummingbot.strategy.cross_exchange_market_making
- wings.web3_wallet
- wings.web3_wallet_backend
- wings.ddex_market
- wings.binance_market
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

---

## Hummingbot configuration variables

The following parameters are fields in Hummingbot configuration files (located in the `/conf` folder, e.g. `conf/conf_*_strategy.yml`).

| Term | Definition |
|------|------------|
| **min_profitability** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%).<br/>Minimum required profitability in order for Hummingbot to place an order on the maker exchange. <br/><br/>*Example: assuming a minimum profitability threshold of `0.01` and a token symbol that has a bid price of 100 on the taker exchange (binance), Hummingbot will place a bid order on the maker exchange (ddex) of 99 (or lower) to ensure a 1% (or better) profit; Hummingbot only places this order if that order is the best bid on the maker exchange.*

### Cross-exchange market making only

| Term | Definition |
|------|------------|
| **active_order_canceling** | `True` or `False`<br/>If enabled (parameter set to `True`), Hummingbot will cancel that become unprofitable based on the `min_profitability` threshold.  If this is set to `False`, Hummingbot will allow any outstanding orders to expire, unless `cancel_order_threshold` is reached.
| **cancel_order_threshold** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%), which can be 0 or negative.<br/>When active order canceling is set to `False`, if the profitability of an order falls below this threshold, Hummingbot will cancel an existing order and place a new one, if possible.  This allows the bot to cancel orders when paying gas to cancel (if applicable) is a better than incurring the potential loss of the trade.
| **limit_order_min_expiration** | An amount in seconds, which is the minimum duration for any placed limit orders. _Default value: 130 seconds_.
| **top_depth_tolerance** | An amount expressed in quote currency of maximum aggregate amount of orders at a better price than Hummingbot's order that are allowed before Hummingbot modifies its order.<br/><br/>*Example: assuming a top depth tolerance of `100` and a Hummingbot bid price of 20, if there exist an aggregate amount of orders of more than 100 at a better (higher) price than Hummingbot's bid, Hummingbot will cancel its order at 20 and re-evaluate the next opportunity to place a new bid.*
| **trade_size_override** | An amount expressed in quote currency of maximum allowable order size.  If not set, the default value is 1/6 of the aggregate value of quote and base currency balances across the maker and taker exchanges.<br/><br/>*Example: assuming a trade size override of `100` and a token symbol of ETH/DAI, the maximum allowable order size is one that has a value of 100 DAI.*

<hr />

# Next: [Running bots](/running-bots)