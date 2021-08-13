# Create or Import Config Files

## Creating a new strategy file

Run `create` command and answer the prompts to configure your bot's behavior depending on the strategy you want to use.

The last prompt will ask you to enter a name for the config file. You can also specify the name of your file at the beginning by running `create [file_name]` command.

![](/assets/img/create-file-name.png)

## Config file templates

These configuration files created and used by Hummingbot are saved in the `conf/` directory of your instance, which you can edit directly with a standard text editor.

- Installed from source: `hummingbot/conf`
- Installed via Docker: `hummingbot_files/hummingbot_conf`
  - `hummingbot_files` is the default name of the parent directory. This can be different depending on the setup
    when the instance was created.
- Installed via Binary (Windows): `%localappdata%\hummingbot.io\Hummingbot\conf`
- Installed via Binary (MacOS): `~/Library/Application\ Support/Hummingbot/Conf`

The template configuration files can be found here: [Config Templates](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/templates).

!!! warning
    Exit Hummingbot and ensure it is not running when you modify the config files. Changes will take effect the next time Hummingbot is started.

## Strategy-specific files

Running `create` command initializes the configuration of global and strategy-specific settings necessary to run the bot.

Running this command will automatically create the following files in these folders:

| File                                    | Description                                                                                          |
| --------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `conf_global.yml`                       | Global configuration settings, e.g. Binance API keys and Ethereum node.                              |
| `conf_pure_mm_[#].yml`                  | Settings for the [pure market making](/strategies/pure-market-making/) strategy.                     |
| `conf_xemm_[#].yml`                     | Settings for the [cross-exchange market making](/strategies/cross-exchange-market-making/) strategy. |
| `conf_liquidity_mining_[#].yml`         | Settings for the [liquidity mining](/strategies/liquidity-mining/) strategy.                         |
| `conf_perpetual_market_making_#.yml`    | Settings for the [perpetual market making](/strategies/perpetual-market-making) strategy.            |
| `conf_arb_[#].yml`                      | Settings for the [arbitrage](/strategies/arbitrage/) strategy.                                       |
| `conf_celo_arb_[#].yml`                 | Settings for the [celo arbitrage](/strategies/celo-arb/) strategy.                                   |
| `conf_amm_arb_[#].yml`                  | Settings for the [amm arbitrage](/strategies/amm-arb/) strategy.                                     |
| `conf_spot_perpetual_arbitrage_[#].yml` | Settings for the [spot perpetual arbitrage](/strategies/spot-perpetual-arb/) strategy.               |
| `conf_avellaneda_market_making_[#].yml` | Settings for the [avellaneda market making](/strategies/avellaneda-market-making/) strategy.         |

!!! tip
    For editing configuration files directly, once they are created, you may find it easier to edit the configuration files in the `conf/` folder. Simply open them with a text editor and make any desired modifications.

## Setup walkthrough

After running `create` command, you need to setup a strategy along with its parameters.

We have developed walkthroughs for each strategy:

- [Pure market making](/strategies/pure-market-making)
- [Cross-exchange market making](/strategies/cross-exchange-market-making)
- [Perpetual Market Making](/strategies/perpetual-market-making)
- [Arbitrage](/strategies/arbitrage)
- [Celo Arbitrage](/strategies/celo-arb/)
- [AMM Arbitrage](/strategies/amm-arb/)
- [Liquidity Mining](/strategies/liquidity-mining/)
- [Spot Perpetual Arbitrage](/strategies/spot-perpetual-arb/)
- [Avellaneda Market Making](/strategies/avellaneda-market-making/)

!!! note
    When configuring your bot, make sure you are aware of your exchange's minimum order sizes and fees, and check that your trading pair has sufficient order book and trading volumes. You can find more info about specific exchanges in the [Connectors](/connectors) section.

## Import an existing strategy file

1. Run `import` command
2. Enter the name of your strategy config file

![](/assets/img/import-command.png)

You can also skip the prompt by running `import [file_name]` command.

![](/assets/img/import-file-name.png)

!!! tip
    Press **TAB** to scroll through the auto-complete selections.

## Autofill import

Choose between `start` and `config` after importing a strategy file. This will be applicable for all imported strategies.

Prompt:

```
What to auto-fill in the prompt after each import command? (start/config) >>>
```

**Sample usage**

`autofill_import = start`

```
>>>`import conf_pure_mm_1.yml`
Configuration from conf_pure_mm_1.yml file is imported.

Preliminary checks:
 - Exchange check: All connections confirmed.
 - Strategy check: All required parameters confirmed.
 -All checks: Confirmed.

Enter "start" to start market making

>>> start

```

Here's an example if using the config command
`autofill_import = config`

```
>>>`import conf_pure_mm_1.yml`
Configuration from conf_pure_mm_1.yml file is imported.

Preliminary checks:
 - Exchange check: All connections confirmed.
 - Strategy check: All required parameters confirmed.
 -All checks: Confirmed.

Enter "start" to start market making

>>> config

```

## Create command shortcuts

To use this feature, open and configure `conf_global.yml`.

Import the lines of code to create a custom command shortcut.

```
# Command Shortcuts
# Define abbreviations for often used commands
# or batch grouped commands together

command_shortcuts:
  # Assign shortcut command
  command: spreads_refresh

  # Reference
  help: Set bid spread, ask spread, and order refresh time

  # Argument Label
  arguments: [Bid Spread, Ask Spread, Order Refresh Time]

  # Original config output with value
  output: [config bid_spread $1, config ask_spread $2, config order_refresh_time $3]
```

!!! note
    Custom made commands can only be used once a strategy has been imported.

![Custom Script Instructions](/assets/img/script-command.gif)
