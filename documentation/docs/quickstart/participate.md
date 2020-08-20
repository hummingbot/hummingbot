# Quickstart - Run the bot in paper trading mode

0. [Overview](index.md)
1. [Install Hummingbot](install.md)
2. [Configure a market making bot](configure.md)
3. [Run the bot in paper trading mode](run-bot.md)
4. Participate in Liquidity Mining

---

If you have successfully configured a pure market making bot in step 3, and wants to proceed with liquidity mining, you need to sign up [Miner App](https://miners.hummingbot.io/) and add the read-only exchange keys in order for the Miner App to check if if there are valid open orders that are eligible for rewards.

<b>Prerequiste:</b> Your Ethereum wallet address. The Hummingbot Miners app uses your Ethereum wallet address to:

* Assign you a unique user ID. The Hummingbot miners app associates your configurations (e.g. email address, API configurations), as well as activity. This allows the miners app to display your user-specific information such as rewards earned and payout history.
* Send you token payouts: mining rewards payouts will be sent to this address

<b>Note:</b>Wallet is not used for trading and only used for the purposes mentioned above, you do not need deposit assets into or trade using this wallet.</ul></small>

To do so:

1. Go to [https://miners.hummingbot.io/](https://miners.hummingbot.io/).
2. Click **Sign up** on the upper-right corner of the website.
3. Enter your email address, read and agree to the terms of service and **Create account**
4. Check your e-mail and click **Log in to Hummingbot Miner**. <b>Note:</b> 
    - If your Ethereum wallet is connected, it will automatically register to the account you just created.This Ethereum wallet is where your rewards are sent every week during payout.
    - Check the Ethereum address by going to the **Settings** page.
    - You can do more in the **Settings** page like changing Ethereum address, adding your API keys, display name (optional), and subscribed/unsubscribe to e-mails. For more details, see [Settings](/minerapp/settings.md)
5. In the **Settings** page, click **DETAILS** in the **Connect exchange** row.
6. Click **Connect binance**
7. Enter your READ-ONLY keys.
8. Click **Connect** .It will show the status when you have successfully added your Binance API keys
9. You can view the rewards, payout, and performance in [https://miners.hummingbot.io/dashboard](https://miners.hummingbot.io/dashboard)


<b>Important:</b>If you just started running a new bot, it takes up to 1 hour for our system to pick up your bot's activity before you start seeing rewards. This warm-up period lets us automate the collection process without polling every order book for every user's bot.


---

🎉🎉🎉 **Congratulations on successfully completing the Liquidity Mining Quickstart!**

