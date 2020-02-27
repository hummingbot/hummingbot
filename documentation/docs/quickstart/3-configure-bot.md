# [Quickstart] Configure Your First Trading Bot

If you have successfully installed Hummingbot using our install scripts, you should see the command line-based Hummingbot interface below.

![](/assets/img/hummingbot-cli.png)

## Step 1: Navigate the Client Interface

First, let's walk through the design of the Hummingbot client interface:

* Left top pane: where the responses to your commands are printed
* Left bottom pane: where you input [commands](/operation/client/#user-interface) to control your bot
* Right pane: where logs of live trading bot activity are printed

**Enter `help` to see a list of commands:**

```
config              Add your personal credentials e.g. exchange API keys  
exit                Securely exit the command line                        
export_private_key  Print your account private key                        
export_trades       Export your trades to a csv file                      
get_balance         Print balance of a certain currency                   
help                Print a list of commands                              
history             Get your bot's past trades and performance analytics  
list                List global objects                                   
paper_trade         Enable / Disable paper trade mode.                    
start               Start market making with Hummingbot                   
status              Get current bot status                                
stop                Stop the bot's active strategy
```

## Step 2: Enable Paper Trading Mode (Optional)

You can run Hummingbot and simulate trading strategies without executing and placing actual trades. Run command `paper_trade` at the beginning to enable this feature.

```
Enable paper trading mode (Yes/No) ? >>> Yes

New config saved:
paper_trade_enabled: Yes

Your configuration is incomplete. Would you like to proceed and finish all necessary configurations? (Yes/No) >>> No
```

For more information about this feature, see [Paper Trading Mode](/utilities/paper-trade) in the User Manual. To perform actual trading, proceed to the next step.


## Step 3: Configure a market making bot

Now, let's walk through the process of configuring a basic market making bot. Enter `config` command to start the configuration walkthrough.

!!! warning
    Values of parameters from here on are indicative for illustrative purposes only; this is not financial advice.

![config_pmm](/assets/img/config_pmm1.gif)

#### a) Setting up a password

If setting up Hummingbot for the first time, the system will prompt:

```
Enter your new password >>> ****

Please reenter your password >>> ****
```

This password will be used to encrypt sensitive configuration settings e.g. API keys, secret keys and wallet private keys. Please note, for security reasons the system does not store your password anywhere. So in case of forgotten password, there is no way to recover it.

#### b) Select strategy and configs

Next, we'll create a configuration for the [pure market making](/strategies/pure-market-making) strategy which makes a market on a single trading pair.

```
What is your market making strategy >>>
pure_market_making

Import previous configs or create a new config file? (import/create) >>>
create
```

!!! tip "Tip: Autocomplete Inputs during Configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.

#### c) Select an exchange and trading pair

Next, select which exchange and trading pair you want to use. Note that you may need an exchange account and inventory of crypto assets deposited on the exchange. You can view more information in [Connectors Overview](https://docs.hummingbot.io/connectors/) about the exchanges Hummingbot currently supports.

You can select a centralized exchange like Binance:
```
Enter your maker exchange name >>>
binance

Enter the token symbol you would like to trade on binance (e.g. ZRX-ETH) >>>
ETH-USDT
```

Alternatively, you can select a decentralized exchange like Radar Relay:
```
Enter your maker exchange name >>>
radar_relay

Enter the token symbol you would like to trade on radar_relay (e.g. ZRX-WETH) >>>
ZRX-WETH
```


#### d) Enter market making parameters

Parameters control the behavior of your bot by setting the spread utilized, the size of each order, how many orders to place, and how often to refresh orders. These are the basic configurations required for this strategy. You can always run the command `config advanced_mode` to access and configure the advanced parameters.

```
How far away from the mid price do you want to place the first bid order? (Enter 0.01 to indicate 1%) >>>
0.01

How far away from the mid price do you want to place the first ask order? (Enter 0.01 to indicate 1%) >>>
0.01

How often do you want to cancel and replace bids and asks (in seconds)? >>>
60.0

What is the amount of [base_asset] per order? (minimum [min_amount]) >>>
0.2

Would you like to proceed with advanced configuration? (Yes/No) >>>
No
```

A more detailed explanation of each prompt for pure market making strategy are explained [here](/strategies/pure-market-making/#configuration-walkthrough) in the User Manual.


#### e) Enter API keys / Ethereum wallet and node

Now that you have set up how your market making bot will behave, it's time to provide it with the necessary API keys (for centralized exchanges) or wallet/node info (for decentralized exchanges) that it needs to operate.

If you selected a centralized exchange like Binance in step 3c, you will need to:
```
Enter your Binance API key >>>
******************************

Enter your Binance API secret >>>
******************************
```
For more information on how to find your API keys, please see [API Keys](/installation/api-keys).

!!! tip "Tip: Copying and Pasting"
    Users have reported not being able to copy and paste their API keys on some platforms. Our help articles such as [How to copy and paste in Docker Toolbox (Windows)](/support/how-to/#how-to-copy-and-paste-in-docker-toolbox-windows) and [Paste items from clipboard in PuTTY](/support/how-to/#paste-items-from-clipboard-in-putty) may help, and our 24/7 support team can help you if you join our [Discord](https://discord.hummingbot.io).

---

Alternatively, if you selected a decentralized exchange like Bamboo Relay, or Radar Relay in Step 3c:

```
Would you like to import an existing wallet or create a new wallet? (import/create) >>>
import

Your wallet private key >>>
******************************
```

More information in User Manual about [Ethereum wallet](/installation/wallet) and [Ethereum node](/installation/node/node).


#### f) Configure kill switch

[Kill switch](/utilities/kill-switch/) automatically stops the bot after a certain performance threshold, which can be either positive or negative.

Activate the kill switch feature and tell it to stop the strategy when it reaches a specific % loss:

```
Would you like to enable the kill switch? (Yes/No) >>>  
Yes

At what profit/loss rate would you like the bot to stop? (e.g. -0.05 equals 5% loss) >>>
-0.05
```

Hummingbot comes with other useful utilities that help you run the bot such as [exchange rates](/utilities/exchange-rates/) and [Telegram integration](/utilities/telegram/). For more information on these utilities, see the Utilities section in the [User Manual](/manual).


#### g) Sending error logs

Hummingbot requests error logs for the sole purpose of debugging and continuously improving our software. We'll never share the data with a third party.

Enter `Yes` to allow sending error logs to Hummingbot or enter `No` to disable this feature so no data will be collected.

```
Would you like to send error logs to hummingbot? (Yes/No) >>> Yes
```

---

Congratulations! You have successfully set up your first market making bot. You should now see:
```
Config process complete. Enter "start" to start market making.

>>> start
```

## (Optional) Adjusting Parameters

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
* **Docker installations**: Please see [this article](/support/how-to/#how-to-find-out-where-the-config-and-log-files-are-on-hummingbot-installed-via-docker)

#### Root folder layout
```
Hummingbot/
└── conf/   # configuration files
└── logs/   # log files
└── data/   # database of executed trades
```

---
# Next: [Run Your First Trading Bot](/quickstart/4-run-bot)
