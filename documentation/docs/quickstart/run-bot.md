# Quickstart - Run the bot in paper trading mode

0. [Overview](index.md)
1. [Install Hummingbot](install.md)
2. [Configure a market making bot](configure.md)
3. Run the bot in paper trading mode

---

If you have successfully configured a pure market making bot in step 3, you should see the following message in the left pane of Hummingbot:

![](/assets/img/quickstart_start.png)

## Start bot

Make sure that Paper Trading mode is on. The top bar in the Hummingbot client should say `paper_trade: ON`.

![](/assets/img/quickstart_paper_on.png)

Now that you have successfully configured a trading bot, you can start market making by running the `start` command.

![](/assets/img/quickstart_starting.png)

## Run bot
After some preliminary checks, the bot will fetch the current state of the order book and start placing orders.

In paper trading mode, the bot uses live order book data and real trades to determine how to place orders and which orders are filled. However, the bot does not actually place orders. The bot assumes the following starting balance of assets, which can be adjusted in `conf_global.yml`:

* ETH: 10
* USDT: 1000
* USDC: 1000

You should see messages like this in the right-hand log pane.
![](/assets/img/running-bot.png)

## Get bot status

Enter the command `status`. You can also use the **Ctrl-S** keyboard shortcut.

This command shows you:

* **Preliminary checks**: Checks to ensure that the bot is able to run
* **Assets**: How much of each asset you have
* **Active orders**: List of the current open orders
* **Warnings**: Warnings that may impact how your bot runs.

If you don't see any active orders, check that you have correctly entered API keys for the exchange.

## See past trades and performance

Enter the command `history`.

This command shows you:

* **List of trades**: The trades your bot has performed during this session
* **Inventory**: How your inventory has changed as a result of these trades
* **Performance**: How much profit or loss your bot has made as a result of these trades

For more information on how Hummingbot calculates performance, refer to [Performance Analysis](https://docs.hummingbot.io/operation/commands/history/#how-it-works).

## Exit Hummingbot

Enter `stop` to stop the bot, or `exit` to stop and also exit Hummingbot.

![](/assets/img/quickstart_stop.png)

Both `stop` and `exit` automatically cancels all outstanding orders and notifies you if it believes that there are potentially uncancelled orders.

![](/assets/img/quickstart_exit.png)

When you restart Hummingbot, you can import your saved configuration file, which was automatically named `conf_pure_mm_1.yml`:

![](/assets/img/quickstart_import.png)

---

🎉🎉🎉 **Congratulations on successfully completing the Hummingbot Quickstart!**

To get the most out of Hummingbot, consult the following resources:

* [Command Reference](/operation/commands/) for quick reference on useful commands
* [Video Tutorials](https://hummingbot.io/videos/) for tips and tricks in running trading bots
