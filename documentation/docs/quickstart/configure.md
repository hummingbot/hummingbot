# Quickstart - Configure a market making bot

0. [Overview](index.md)
1. [Install Hummingbot](install.md)
2. Configure a market making bot
3. [Run the bot in paper trading mode](run-bot.md)

---

If you have successfully installed Hummingbot using our install scripts, you should see the command line-based Hummingbot interface below. 

![](/assets/img/hummingbot-cli.png)

## Navigate the client interface

First, let's walk through the design of the Hummingbot client interface:

* **Left top pane**: command output pane
* **Left bottom pane**: command input pane
* **Right pane**: trading logs

Enter the command `help` to see a list of commands:
```
config              Create a new bot or import an existing configuration
help                List the commands and get help on each one          
start               Start your currently configured bot                 
stop                Stop your currently configured bot                  
status              Get the status of a running bot                     
history             List your bot's past trades and analyze performance 
exit                Exit and cancel all outstanding orders              
list                List global objects like exchanges and trades       
paper_trade         Toggle paper trade mode                             
export_trades       Export your bot's trades to a CSV file              
export_private_key  Export your Ethereum wallet private key             
get_balance         Query your balance in an exchange or wallet         
```

## Enable paper trading mode

In this Quickstart guide, we will run Hummingbot in paper trading mode and simulate trading strategies without executing and placing actual trades. 

Enter the command `paper_trade` to enable this feature.
```
>>> paper_trade

Enable paper trading mode (Yes/No) ? >>> Yes

New config saved:
paper_trade_enabled: Yes

Your configuration is incomplete. Would you like to proceed and finish all necessary configurations? (Yes/No) >>> No
```

## Create a secure password

Enter the command `config` to configure a new market making bot. 

If you are using Hummingbot for the first time on this machine, the system will prompt you to enter a password. This password will be used to encrypt sensitive configuration settings e.g. API keys, secret keys and wallet private keys. 

```
>>> config

Enter your password >>> *****

Please reenter your password >>> *****
```

!!! warning
    For security reasons, the password is only stored locally in encrypted form. **We do not have access to your password.**

## Create a new configuration

Next, we'll create a configuration for a market making bot using the [pure market making](/strategies/pure-market-making) strategy.

This configuration will be saved to a file that can be imported later on.
```
What is your market making strategy >>>
pure_market_making

Import previous configs or create a new config file? (import/create) >>>
create
```

## Select exchange and trading pair

Next, select the exchange and trading pair. 

Since we are creating a paper trading bot, you don't need any assets on the exchange. However, you will need an account in order to generate API keys.

For the trading pair, select either `ETH-USDT` or `ETH-USDC` depending on the exchange. Here are two examples:

**Binance.com**
```
Enter your maker exchange name >>>
binance

Enter the token symbol you would like to trade on binance (e.g. ZRX-ETH) >>>
ETH-USDT
```

**Coinbase Pro**
```
Enter your maker exchange name >>>
coinbase_pro

Enter the token symbol you would like to trade on binance (e.g. ZRX-ETH) >>>
ETH-USDC
```

## Enter market making parameters

A bot's strategy parameters control how it behaves. During this step, you will define the basic parameters for your market making bot: order spreads, order sizes, and how often to refresh orders.

!!! tip "Tip: What spreads should I set?"
    Order spread is one of the most important levers that market makers can control. Tighter spreads cause your orders to be filled more often, resulting in more trades, bigger changes in asset balance, and potentially more risk. 
    
    We recommend that new users start with **wider spreads**, such as 1.00% for each side of the order book or higher.

```
How far away from the mid price do you want to place the first bid order? (Enter 0.01 to indicate 1%) >>>
0.01

How far away from the mid price do you want to place the first ask order? (Enter 0.01 to indicate 1%) >>>
0.01

How often do you want to cancel and replace bids and asks (in seconds)? >>>
30.0

What is the amount of [base_asset] per order? (minimum [min_amount]) >>>
1
```

Later, you can run the command `config advanced_mode` to access and configure the advanced parameters. A more detailed explanation of each prompt for pure market making strategy are explained [here](/strategies/pure-market-making/#configuration-walkthrough) in the User Manual.

## Enter API keys

Now that you have set up how your market making bot will behave, it's time to provide it with the API keys that it needs to access your exchange account.

Note that each exchange has a different format for API keys. For exchange-specific information on how to find your API keys, please see the individual exchange pages in [Connectors](/connectors).

**Binance.com**
```
Enter your Binance API key >>>
******************************

Enter your Binance API secret >>>
******************************
```

**Coinbase Pro**
```
Enter your Coinbase API key >>>
******************************

Enter your Coinbase secret key >>>
******************************

Enter your Coinbase passphrase >>>
******

```

!!! tip "Tip: Copying and Pasting"
    Users have reported not being able to copy and paste their API keys on some platforms. Our help articles such as [Other ways to copy and paste](/faq/troubleshooting/#other-ways-to-copy-and-paste) and [Paste items from clipboard in PuTTY](/faq/troubleshooting/#paste-items-from-clipboard-in-putty) may help.

---

## Complete and save configuration

Complete the configuration process: 
```
Would you like to enable the kill switch? (Yes/No) >>>  
No

Would you like to send error logs to hummingbot? (Yes/No) >>> 
Yes

Config process complete. Enter "start" to start market making.
>>> start
```

The [Kill Switch](/advanced/kill-switch/) automatically stops the bot after a certain performance threshold, which can be either positive or negative. You can learn about this feature and other advanced features in the **Advanced** section in the sidebar.

---
You should now see:
```
Config process complete. Enter "start" to start market making.
```

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
