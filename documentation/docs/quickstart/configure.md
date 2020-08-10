# Quickstart - Configure a market making bot

0. [Overview](index.md)
1. [Install Hummingbot](install.md)
2. Configure a market making bot
3. [Run the bot in paper trading mode](run-bot.md)

---

If you have successfully installed Hummingbot you should see the welcome screen, read through the important disclaimer and create a secure password. 

## Create a secure password

If you are using Hummingbot for the first time on this machine, the system will prompt you to create a password. This password will be used to encrypt sensitive configuration settings e.g. API keys, secret keys and wallet private keys. 

![](/assets/img/welcome.gif)

!!! warning
    For security reasons, the password is only stored locally in encrypted form. **We do not have access to your password.**


## Navigate the client interface

After setting up your password, you should see the command line-based Hummingbot interface.

![](/assets/img/hummingbot-cli.png)


First, let's walk through the design of the Hummingbot client interface:

* **Left top pane**: command output pane
* **Left bottom pane**: command input pane
* **Right pane**: trading logs

Enter the command `help` to see a list of commands:

| Command | Function |
|---------|----------|
| `connect` | List available exchanges and add API keys to them |
| `create` | Create a new bot |
| `import` | Import a existing bot by loading the configuration file |
| `help` | List available commands |
| `balance` | Display your asset balances across all connected exchanges |
| `config` | Display the current bot's configuration |
| `start` | Start the current bot |
| `stop` | Stop the current bot |
| `status` | Get the market status of the current bot |
| `history` | See the past performance of the current bot |
| `exit` | Exit and cancel all outstanding orders |
| `paper_trade` | Toggle paper trading mode |
| `export` | Export your bot's trades or private keys |

## Enter API keys

Hummingbot requires **trade enabled** API keys to access your exchange account. If you wish to test Hummingbot and simulate trading without risking actual assets, proceed to [enable paper trading mode](#enable-paper-trading-mode).

Enter the command `connect [exchange]` to connect your exchange account to Hummingbot by adding API keys, where `[exchange]`is one of the exchanges supported by Hummingbot. You can hit SPACE or start typing to see available options.

![](/assets/img/connect.gif)

The command `connect` shows if API keys have been successfully added.

Note that each exchange has a different format for API keys. For exchange-specific information on how to find your API keys, please see the individual exchange pages in [Connectors](/connectors).

!!! tip "Tip: Copying and Pasting"
    Users have reported not being able to copy and paste their API keys on some platforms. Our help articles such as [Other ways to copy and paste](/faq/troubleshooting/#other-ways-to-copy-and-paste) and [Paste items from clipboard in PuTTY](/faq/troubleshooting/#paste-items-from-clipboard-in-putty) may help.

## Enable paper trading mode

In this Quickstart guide, we will run Hummingbot in paper trading mode and simulate trading strategies without executing and placing actual trades.

If you wish to use Hummingbot using real assets and place live orders, [skip this step](/#create-a-new-configuration).

Enter the command `paper_trade` to enable this feature.

<img src="/assets/img/paper_trade.gif" alt="Binance Trading Pair"  width="600" />

## Create a new configuration

Next, we'll create a configuration for a market making bot using the [pure market making](/strategies/pure-market-making) strategy.

Enter the command `create` to begin creating a strategy config file. This configuration will be saved to a file that can be imported later on.

<img src="/assets/img/quickstart_create.gif" alt="Binance Trading Pair"  width="600" />

## Select exchange and trading pair

Next, select the exchange and trading pair. 

Since we are creating a paper trading bot, you don't need any assets on the exchange. However, you will need an account in order to generate API keys.

For the trading pair, select either `ETH-USDT` or `ETH-USDC` depending on the exchange. Here are two examples:

**Binance.com**

<img src="/assets/img/quickstart_binance.png" alt="Binance Trading Pair"  width="800" />

**Coinbase Pro**

<img src="/assets/img/quickstart_coinbase_pro.png" alt="Coinbase Pro Trading Pair"  width="800" />


## Enter market making parameters

A bot's strategy parameters control how it behaves. During this step, you will define the basic parameters for your market making bot: order spreads, order sizes, and how often to refresh orders.

!!! tip "Tip: What spreads should I set?"
    Order spread is one of the most important levers that market makers can control. Tighter spreads cause your orders to be filled more often, resulting in more trades, bigger changes in asset balance, and potentially more risk. 
    
    We recommend that new users start with **wider spreads**, such as 1.00% for each side of the order book or higher.

<img src="/assets/img/quickstart_configure1.png" alt="Pure-mm Parameters"  width="800" />

Later, you can access and configure the advanced parameters of this strategy. A more detailed explanation of each prompt for basic pure market making strategy are explained [here](/strategies/pure-market-making/#configuration-walkthrough) and advanced market making [here](/strategies/advanced-mm/#advanced-configuration-parameters).


## Alternate buy and sell orders

The ping pong feature helps users in managing inventory risk by alternating buy and sell orders after a fill.

![](/assets/img/quickstart_pingpong.png)

For more information, you may read through [Ping Pong](/strategies/advanced-mm/ping-pong) in the Advanced Market Making section.


## Save configuration

Enter the name you want for your configuration file to complete the process.

![](/assets/img/quickstart_start.png)

Proceed to the next section: [Run Your First Trading Bot](run-bot.md)


<!-- ## (Optional) Adjusting Parameters

### From the Hummingbot client

If you want to reconfigure the bot from the beginning, type `config` and reply `y` to the question `Would you like to reconfigure the bot? (Yes/No) >>>?`. This will prompt all questions during initial setup.

Alternatively, the command `list configs` will show your current bot's configuration.

```
>>> list configs

global configs:
...

pure_market_making strategy configs:

maker_market                    binance
primary_market_trading_pair     ETH-USDT
bid_place_threshold             0.01
ask_place_threshold             0.01
cancel_order_wait_time          60.0
order_amount                    0.2
...

```

You can change a parameter by with the command `config [parameter_name]`.

For example, let's widen the `bid_place_threshold` to 0.02. This tells the bot to place buy order 2% lower than the mid price, rather than 1%:

```
>>> config bid_place_threshold

Please follow the prompt to complete configurations:

How far away from the mid price do you want to place the first bid order (Enter 0.01 to indicate 1%)? >>>
0.02

New config saved:
bid_place_threshold: 0.02

```

### From the command line

When you configure a bot, Hummingbot automatically saves the configuration file so that you can import it the next time you run Hummingbot. If you go to the Hummingbot root folder, you can edit these configuration files directly.

#### Root folder location

* **Windows**: `%localappdata%\hummingbot.io\Hummingbot`
* **macOS**: `~/Library/Application\ Support/Hummingbot`
* **Docker installations**: Please see [this article](/faq/troubleshooting/#where-are-the-config-and-log-files-on-hummingbot-installed-docker)

#### Root folder layout
```
Hummingbot/
└── conf/   # configuration files
└── logs/   # log files
└── data/   # database of executed trades
``` -->
