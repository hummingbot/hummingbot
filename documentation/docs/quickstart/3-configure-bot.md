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
bounty              Participate in hummingbot's liquidity bounty programs 
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
Enable paper trading mode (y/n) ? >>> y

New config saved:
paper_trade_enabled: y

Your configuration is incomplete. Would you like to proceed and finish all necessary configurations? (y/n) >>> n
```

For more information about this feature, see [Paper Trading Mode](/utilities/paper-trade) in the User Manual. To perform actual trading, proceed to the next step.


## Step 3: Configure a market making bot

Now, let's walk through the process of configuring a basic market making bot.

!!! tip "Tip: Autocomplete Inputs during Configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.

#### a) Enter `config` to start the configuration walkthrough

If setting up Hummingbot for the first time, the system will prompt:

```
Enter your new password >>> ****

Please reenter your password >>> ****
```

This password will be used to encrypt sensitive configuration settings e.g. api keys, secrets and wallet private keys. Please note, for security reason, the system does not store your password anywhere, so in case of forgotten password, there is no way to recover it.

Next, we'll create a configuration for the [pure market making](/strategies/pure-market-making) strategy which makes a market on a single trading pair.

!!! warning
    Values of parameters from here on are indicative for illustrative purposes only; this is not financial advice.

```
What is your market making strategy >>>
pure_market_making

Import previous configs or create a new config file? (import/create) >>>
create
```

#### b) Select the exchange and trading pair

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


#### c) Enter market making parameters

Parameters control the behavior of your bot by setting the spread utilized, the size of each order, how many orders to place, and how often to refresh orders. A more detailed explanation of each prompt for pure market making strategy are explained [here](/strategies/pure-market-making/#configuration-walkthrough) in the User Manual.

```
Enter quantity of bid/ask orders per side (single/multiple) >>>
single

How far away from the mid price do you want to place the first bid order? (Enter 0.01 to indicate 1%) >>>
0.01

How far away from the mid price do you want to place the first ask order? (Enter 0.01 to indicate 1%) >>>
0.01

How often do you want to cancel and replace bids and asks (in seconds)? (Default is 60 seconds) >>>
60

What is your preferred quantity per order? (Denominated in the base asset, default is 1) >>>
0.2

How long do you want to wait before placing the next order if your order gets filled (in seconds)? (Default is 10 seconds) >>>
10

Do you want to enable order_filled_stop_cancellation? If enabled, when orders are completely filled, the other side remains uncanceled. (Default is False) >>> 
False

Do you want to enable jump_orders? If enabled, when the top bid price is lesser than your order price, buy order will jump to one tick above top bid price & vice versa for sell. (Default is False) >>>
False

Do you want to add transaction costs automatically to order prices? (Default is True) >>>
True

```

#### d) Enable inventory skew

This function allows you to set a target base/quote inventory ratio. For example, you are trading ZRX-WETH pair while your current asset inventory consists of 80% ZRX and 20% WETH. Setting this to 0.5 will allow the bot to automatically adjust the order amount on both sides, selling more and buying less ZRX until you get a 50%-50% ratio.

```
Would you like to enable inventory skew? (y/n) >>>
y

What is your target base asset inventory percentage? (Enter 0.01 to indicate 1%, Default is 0.5 (50%)) >>>
0.5
```

Here's an [inventory skew calculator](https://docs.google.com/spreadsheets/d/16oCExZyM8Wo8d0aRPmT_j7oXCzea3knQ5mmm0LlPGbU/edit#gid=690135600) that shows how it adjusts order sizes.


#### e) Enter your exchange API keys OR Ethereum wallet/node info

Now that you have set up how your market making bot will behave, it's time to provide it with the necessary API keys (for centralized exchanges) or wallet/node info (for decentralized exchanges) that it needs to operate:

!!! note "Copying and Pasting"
    Our Get Help section contains answers to some of the common how-to questions like [How do I copy and paste in Docker Toolbox?](/support/how-to/#how-do-i-copy-and-paste-in-docker-toolbox-windows) and [How do I paste items from clipboard in PuTTY?](support/how-to/#how-do-i-paste-items-from-clipboard-in-putty)

If you selected a centralized exchange like Binance in Step 3(b), you will need to :
```
Enter your Binance API key >>>
******************************

Enter your Binance API secret >>>
******************************
```
For more information on how to find your API keys, please see [API Keys](/installation/api-keys).

---

Alternatively, if you selected a decentralized exchange like IDEX, DDEX, Bamboo Relay, or Radar Relay in Step 3(b):
```
Would you like to import an existing wallet or create a new wallet? (import/create) >>>
import

Your wallet private key >>>
******************************

A password to protect your wallet key >>>
[ENTER A SECURE PASSWORD THAT UNLOCKS THIS WALLET FOR EACH HUMMINGBOT SESSION]

Which Ethereum node would you like your client to connect to? >>>
[ENTER ADDRESS OF YOUR ETHEREUM NODE]
```

More information in User Manual about [Ethereum wallet](/installation/wallet) and [Ethereum node](/installation/node/node).


#### f) Enter kill switch parameters

Hummingbot comes with utilities that help you run the bot, such as:

* [**Kill switch**](/utilities/kill-switch/): Automatically stops the bot after a certain performance threshold, which can be either positive or negative
* [**Exchange rates**](/utilities/exchange-rates/): Sets exchange rates between stablecoins and other crypto assets so that you can run bots on non-identical trading pairs on different exchanges
* [**Telegram integration**](/utilities/telegram/): Control your trading bot from anywhere by hooking up a Telegram bot that can issue commands

For more information on these utilities, see the Utilities section in the [User Manual](/manual). By default, only the **kill switch** is configured via the walkthrough.


Activate the kill switch feature and tell it to stop the bot when it reaches a specific % loss:
```
Would you like to enable the kill switch? (y/n) >>>  
y

At what profit/loss rate would you like the bot to stop? (e.g. -0.05 equals 5% loss) >>>
-0.05
```

## Step 4: Adjusting Parameters

If you want to reconfigure the bot from the beginning, type `config` and reply `y` to the question `Would you like to reconfigure the bot? (y/n) >>>?`. This will prompt all questions during initial set up.

Alternatively, the command `list configs` will show your current bot parameters both global and the strategy configs.

```
>>> list configs

global configs:
...

pure_market_making strategy configs:
...
mode                      single
bid_place_threshold       0.01
ask_place_threshold       0.01
cancel_order_wait_time    60
order_amount              0.2
...

```

You can specify which parameter you want to configure by doing `config $parameter_name`. As an example, we want to widen the `bid_place_threshold` to 0.02. This tells the bot to place buy order 2% lower than the mid price, rather than 1%.

```
>>> config bid_place_threshold

Please follow the prompt to complete configurations:

How far away from the mid price do you want to place the first bid order (Enter 0.01 to indicate 1%)? >>>
0.02

New config saved:
bid_place_threshold: 0.02

```

You can also exit the bot with `exit` and edit the automatically generated configuration file `conf_pure_market_making_0.yml`. This file is saved in the directory `hummingbot_files/hummingbot_conf/` in your root. For more information, see [Troubleshooting](/support/how-to/#how-do-i-edit-the-conf-files-or-access-the-log-files-used-by-my-docker-instance).


---
If you completed the steps above successfully, you should see the message:
```
Config process complete. Enter "start" to start market making.

>>> start
```


---
# Next: [Run Your First Trading Bot](/quickstart/4-run-bot)
