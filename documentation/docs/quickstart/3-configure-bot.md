# [Quickstart] Configure Your First Trading Bot

!!! note "Paper trading mode [in progress]"
    We are currently working on a paper trading mode that will allow you to test out Hummingbot without risking real crypto. For now, you still need to run a live trading bot.

If you have successfully installed Hummingbot using our install scripts, you should see the command line-based Hummingbot interface below.

![](/assets/img/hummingbot-cli.png)

## Step 1: Navigate the Client Interface

First, let's walk through the design of the Hummingbot client interface:

* Left top pane: where the responses to your commands are printed
* Left bottom pane: where you input [commands](https://docs.hummingbot.io/operation/client/#client-commands) to control your bot
* Right pane: where logs of live trading bot activity are printed

**Enter `help` to see a list of commands:**
```
>>> help
help    Print a list of commands
start   Start market making with Hummingbot
config  Add your personal credentials e.g. exchange API keys
status  Get current bot status
bounty  Participate in hummingbot's liquidity bounty programs

etc...
```

## Step 2: Register for Liquidity Bounties (Optional)

Liquidity Bounties allow you to earn rewards by running market making bots for specific tokens and/or exchanges.

Hummingbot enters into partnerships with token issuers and exchanges to administer bounty programs that reward Hummingbot users based on their volume of filled market maker orders. For more information, please see [Bounties FAQ](/bounties/faq).

**Enter `bounty --register` to start the registration process:**

1. Agree to the Terms & Conditions
2. Allow us to collect your trading data for verification purposes
3. Enter your Ethereum wallet address
4. Enter your email address
5. Confirm information and finalize

Note that in order to accumulate rewards, you need to maintain at least 0.05 ETH in your Ethereum wallet. This prevents spam attacks and ensures that everyone has a fair chance to earn bounties.

## Step 3: Configure a market making bot

Now, let's walk through the process of configuring a basic market making bot.

!!! tip "Tip: Autocomplete Inputs during Configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.

#### a) Enter `config` to start the configuration walkthrough
We'll create a configuration for the `pure market making` strategy, which makes a market on a single trading pair:

```
What is your market making strategy >>>
pure_market_making

Import previous configs or create a new config file? (import/create) >>>
create
```

#### b) Select the exchange and trading pair

Next, select which exchange and trading pair you want to use. Note that you may need an exchange account and inventory of crypto assets deposited on the exchange.

You can select a centralized exchange like Binance:
```
Enter your maker exchange name >>>
binance

# Change this selection based on what tokens you own
Enter the token symbol you would like to trade on binance (e.g. ZRXETH) >>>
ETHUSDT
```

Alternatively, you can select a decentralized exchange like IDEX:
```
Enter your maker exchange name >>>
idex

# Change this selection based on what tokens you own
Enter the token symbol you would like to trade on idex (e.g. ZRXETH) >>>
DAI_ETH
```

#### c) Enter market making parameters

Parameters control the behavior of your bot by setting the spread utilized, the size of each order, how many orders to place, and how often to refresh orders.

```
Enter quantity of orders per side [bid/ask] (single/multiple) default is single >>>
single

How far away from the mid price do you want to place the first bid order (Enter 0.01 to indicate 1%)?| >>>
0.01

How far away from the mid price do you want to place the first ask order (Enter 0.01 to indicate 1%)?| >>>
0.01

How often do you want to cancel and replace bids and asks (in seconds). (Default is 60 seconds) ? >>>|
60

# Enter a quantity based on how many tokens you own
What is your preferred quantity per order (denominated in the base asset, default is 1) ? >>>
0.2
```

#### d) Enter your exchange API keys OR Ethereum wallet/node info

Now that you have set up how your market making bot will behave, it's time to provide it with the necessary API keys (for centralized exchanges) or wallet/node info (for decentralized exchanges) that it needs to operate:

!!! note "Copying and pasting in Windows"
    If you are using a Windows machine, you may need to activate copying and pasting on Docker Toolbox. Please see [this page](/support/troubleshooting/#how-do-i-copy-and-paste-in-docker-toolbox-windows) for instructions on how to activate this.

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

See [Ethereum wallet](/installation/wallet) and [Ethereum node](/installation/node/node) for more information.

#### e) Enter kill switch parameters

Hummingbot comes with utilities that help you run the bot, such as:

* **Kill switch**: Automatically stops the bot after a certain performance threshold, which can be either positive or negative
* **Exchange rates**: Sets exchange rates between stablecoins and other crypto assets so that you can run bots on non-identical trading pairs on different exchanges
* **Telegram integration**: Control your trading bot from anywhere by hooking up a Telegram bot that can issue commands

For more information on these utilities, see the Utilities section in the [User Manual](/manual). By default, only the **kill switch** is configured via the walkthrough.

---
If you completed the steps above successfully, you should see the message:
```
Config process complete. Enter "start" to start market making.

>>> start
```

!!! warning "Help! I mis-typed something and need to start over!"
    Type `config` and reply `y` to the question `Would you like to reconfigure the bot? (y/n) >>>?`

    Alternatively, you can exit the bot with `exit` and edit the automatically generated configuration file `conf_pure_market_making_0.yml`. This file is saved in the directory `hummingbot_files/hummingbot_conf/` in your root. For more info, see [Docker Commands](/cheatsheets/docker).



---
# Next: [Run Your First Trading Bot](/quickstart/4-run-bot)
