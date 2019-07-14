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

## Step 4: Stop the bot

Enter `stop` to stop the bot, or `exit` to stop and also exit Hummingbot. 

Hummingbot automatically cancels all outstanding orders and notifies you if it believes that there are potentially uncancelled orders.

---
Congratulations on successfully completing the Hummingbot quickstart guide! 

To get the most out of Hummingbot, consult the User Manual for more information.