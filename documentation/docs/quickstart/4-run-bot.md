# [Quickstart] Run Your First Trading Bot

Now that you have successfully [configured](/quickstart/2-configure-bot) a trading bot, you can start market making by running the `start` command.

!!! tip
    You can see your Hummingbot open orders in real-time on the exchange website as you run Hummingbot. Generally, we recommend having the exchange website in a browser alongside the running Hummingbot command line interface.

## Step 1: Start bot

Enter `start` to start the market making bot. After some preliminary checks, the bot will fetch the current state of the order book and start placing orders.

You should see messages like the ones below in the log pane:

![](/assets/img/running-bot.png)

If you don't see messages related to order creation, check that:

* You have correctly entered API keys
* You have sufficient balance of both tokens in your trading pair
* You have entered `order_amount` that exceeds the minimum order size for your selected exchange

## Step 2: Get the current bot status

Enter `status` to see the current bot status. You can also use the **Ctrl-S** keyboard shortcut.

This command shows you:

* **Preliminary checks**: Checks to ensure that the bot is able to run
* **Assets**: How much of each asset you have
* **Active orders**: List of the current open orders
* **Warnings**: Warnings that may impact how your bot runs.

!!! note "About warning messages"
    Currently, we default to displaying all warnings, including those related to network and API errors from which Hummingbot may have already gracefully recovered. If the bot appears to be behaving as expected, you may safely ignore certain warnings.

## Step 3: List trades and performance

Enter `history` to see what trades the bot has executed and how well it has performed.

This command shows you:

* **List of trades**: The trades your bot has performed during this session
* **Inventory**: How your inventory has changed as a result of these trades
* **Performance**: How much profit or loss your bot has made as a result of these trades

## Step 4: Exit and restart Hummingbot

#### a) Stop the bot and exit

Enter `stop` to stop the bot, or `exit` to stop and also exit Hummingbot. 

Hummingbot automatically cancels all outstanding orders and notifies you if it believes that there are potentially uncancelled orders.

#### b) Restart Hummingbot

To restart Hummingbot, run the `start.sh` helper script from the command line. This starts and attaches the Docker container.
```
./start.sh
```

## Step 5: Import your saved configuration

Hummingbot automatically saves your **global config file** and **strategy config file**, so you can import these settings without entering them again:

```
hummingbot_files                                  # Top level folder for your instance
└── hummingbot_conf                               # Folder for configuration files (maps to conf/ folder)
    ├── conf_global.yml                           # Auto-saved global config file
    └── conf_pure_market_making_strategy_0.yml    # Auto-saved strategy config file
```

By default, the auto-saved strategy configuration file is named `conf_pure_market_making_strategy_0.yml` in your configuration directory.

#### a) Import configuration

Enter `config` to start the configuration process again, but select `import`:
```
What is your market making strategy >>>
pure_market_making

Import previous configs or create a new config file? (import/create) >>>
import

Enter path to your strategy file (e.g. "conf_pure_market_making_strategy_0.yml") >>> 
conf_pure_market_making_strategy_0.yml

# This question appears only if you are trading on a decentralized exchange
Would you like to unlock your previously saved wallet? (y/n) >>>

Config process complete. Enter "start" to start market making.
```

#### b) Adjust parameters

Rather than just starting the bot as-is, let's adjust one of the parameters.

Enter `list configs` to inspect the current bot parameters, which shows both the global and the strategy configs.

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

Widen the `bid_place_threshold` to 0.02. This tells the bot to place buy order 2% lower than the mid price, rather than 1%.
```
>>> config bid_place_threshold

Please follow the prompt to complete configurations:

How far away from the mid price do you want to place the first bid order (Enter 0.01 to indicate 1%)? >>>
0.02

New config saved:
bid_place_threshold: 0.02

```

#### c) Restart your market making bot
Similarly, you can adjust other parameters by using the `config` command and specifying the parameter name afterwards.

When you are satisfied with your bot parameters, enter `start` to restart your market making bot.


---
Congratulations on successfully completing the Hummingbot quickstart guide! 

To get the most out of Hummingbot, consult the following resources:

* [Cheatsheets](/cheatsheets) for quick reference on useful commands
* [User Manual](/manual) for in-depth reference on all Hummingbot features
* [Video Tutorials](https://hummingbot.io/videos/) for tips and tricks in running trading bots
