# FAQ

Below is a summary of frequently asked questions regarding Hummingbot.  If you have additional questions or need support, please join the official [Hummingbot Discord server](https://discord.hummingbot.io) or email us at [support@hummingbot.io](mailto:support@hummingbot.io).

## General

### What is Hummingbot?

[Hummingbot](http://hummingbot.io) is open source software that helps you build and run market making bots. For more detailed information, please read the [Hummingbot whitepaper](https://www.hummingbot.io/whitepaper.pdf).

### What is market making?
Market making is the act of simultaneously creating buy and sell orders for an asset in a market. By doing so, a market maker acts as a liquidity provider, facilitating other market participants to trade by giving them the ability to fill the market maker's orders. Traditionally, market making industry has been dominated by highly technical quantitative hedge funds and trading firms who have the infrastructure and intelligence to deploy sophisticated algorithms at scale.

Market makers play an important role in providing liquidity to financial markets, especially in the highly fragmented cryptocurrency industry. While large professional market makers fight over the most actively traded pairs on the highest volume exchanges, there exists a massive **long tail of smaller markets** who also need liquidity: tokens outside the top 10, smaller exchanges, decentralized exchanges, and new blockchains.

In addition, the prohibitively high payment demanded by pro market makers, coupled with lack of transparency and industry standards, creates perverse incentives for certain bad players to act maliciously via wash trading and market manipulation. For more discussion on the liquidity problem, please check out [this blog post](https://www.hummingbot.io/blog/2019-01-thin-crust-of-liquidity/).

### Why are you making Hummingbot available to the general public rather than just running it in-house?

We make money by administering [Liquidity Mining](/liquidity-mining) programs, which allow token projects to source liquidity from a decentralized network rather than from a single firm. Hummingbot is a free tool that anyone can use to participate in liquidity mining.

### Why are you making Hummingbot open source?

- **Trust and Transparency**: In order to use crypto trading bots, users must provide their private keys and exchange API keys. An open source codebase enables anyone to inspect and audit the code.

### How much cryptocurrency do I need to get started?

There is no minimum amount of assets to use Hummingbot, but users should pay heed to exchange-specific minimum order sizes. In our [exchange connectors](/connectors) documentation, we include links to the exchange's minimum order size page where available.

### Are my private keys and API keys secure?

Since Hummingbot is a local client, your private keys and API keys are as secure as the computer you are running them on.  The keys are used to create authorized instructions locally on the local machine, and only the instructions which have already been signed or authorized are sent out from the client.

Always use caution and make sure the computer you are running Hummingbot on is safe, secure, and free from unauthorized access.

### What does it cost for me to run Hummingbot?

Hummingbot is a free software, so you can download, install, and run it for free.

Transactions from Hummingbot are normal transactions conducted on exchanges; therefore when operating Hummingbot, you would be subject to each exchange’s fees (e.g. maker, taker, and withdrawal fees), as you would if you were trading on that exchange normally (i.e. without Hummingbot).

### What data do you collect when I use Hummingbot?

When configuring Hummingbot, you are asked the following question:

```
Would you like to send error logs to hummingbot? (Yes/No) >>>
```

Enter `Yes` to opt-in; enter `No` to opt-out.

## Liquidity Mining

!!! info "Important Disclaimer"
    <small><ul><li>The content of this Site does not constitute investment, financial, legal, or tax advice, nor does any of the information contained on this Site constitute a recommendation, solicitation, or offer to buy or sell any digital assets, securities, options, or other financial instruments or other assets, or to provide any investment advice or service.<li>There is no guarantee of profit for participating in liquidity mining.<li>Participation is subject to eligiblity requirements.</ul></small>
    **Please review the [Liquidity Mining Policy](https://hummingbot.io/liquidity-mining-policy/) for the full disclaimer.**

### What is liquidity mining?
Liquidity mining is a community-based, data-driven approach to market making, in which a token issuer or exchange can reward a pool of miners to provide liquidity for a specified token.

Liquidity mining sets forth an analytical framework for determining market maker compensation based on (1) time (order book consistency), (2) order spreads, and (3) order sizes, in order to create a fair model for compensation that aligns a miner's risk with rewards.

For more information, please read [the whitepaper](https://hummingbot.io/liquidity-mining.pdf).

### Why is it called "liquidity mining"?
Liquidity mining is similar to "*mining*" as used in the broader cryptocurrency context in that: (1) participants are using their own computational resources for market making (e.g., by running the Hummingbot client), and (2) users deploy their own crypto asset inventories (*≈ "staking"*).

In addition, a collective pool of participants are working together for a common goal - in this case to provide liquidity for a specific token and exchange.  In return, miners are paid out rewards corresponding to their “*work*”.  The rules that govern rewards distributions are also clearly and algorithmically defined.

### What strategies can a liquidity miner use?
Liquidity mining rewards are determined based on limit orders created ("maker" orders).  Currently, the Hummingbot client has two strategies that create maker orders:

- [Pure market making (market making on a single exchange)](https://docs.hummingbot.io/strategies/pure-market-making/)
- [Cross-exchange market making](https://docs.hummingbot.io/strategies/cross-exchange-market-making/)

Using either of these two strategies for trading will qualify you to participate in liquidity mining and earn rewards.

### How do you measure liquidity?
We believe that **slippage** is the optimal metric to quantify liquidity, as opposed to filled order volume, a measure widely used by the market. Slippage refers to the difference between the observed mid-market price and the actual executed price for a trade of a given size.  Calculating slippage factors in order book depth and prices at different depths, which better captures the friction and efficiency of actually trading that asset.  Deep, liquid order books have low slippage, while thin, illiquid order books have high slippage.

**We believe slippage is a more robust indicator of liquidity than trading volume**. As an ex-ante metric, slippage measures information used by traders before they trade to decide whether to execute the trade and in which venue to execute it. In contrast, volume is an ex-post metric and can be easily manipulated.

### How are liquidity mining rewards calculated?
In order to make economic sense for a market maker, the market maker’s compensation must correlate with increased levels of risk. There are three main parameters that we use in liquidity mining to determine market maker compensation: (1) **time**: placing orders in the order book consistently over time, (2) **spreads**, and (3) **order sizes**.

In liquidity mining, market makers accumulate more rewards by consistently placing orders over time and earn higher rewards by placing orders with tighter spreads and with larger sizes. The real-time reward information will be displayed in the real-time Hummingbot Miner dashboard.

![](../assets/img/mining-rewards-diagram.jpg)

For more details on the calculation, please read [Demystifying Liquidity Mining Rewards](https://hummingbot.io/blog/2019-12-liquidity-mining-rewards/).

### What are liquidity mining "returns"?

![](../assets/img/miners-return.png)

<small><em>Note: figures above are for illustration only and do not represent current campaign terms; navigate to [Hummingbot Miners](https://miners.hummingbot.io) for current campaign details.</em></small>

The liquidity mining return measures the ratio of rewards in a snapshot compared to the total volume of eligible orders placed in that snapshot.  This displays an overall return for all participants in that snapshot.

The return is represented is an annualized return calculated based on (1) the total amount of mining rewards available for that period, (2) the total volume of eligible orders placed in that period in base currency terms, which is then (3) converted into an annualized rate:

![](../assets/img/lm-return-calculation.png)

This annualized return is what is displayed on the Hummingbot Miner app.

!!! warning "Liquidity mining return does not a represent miner's portfolio return or expected portfolio return."
    Liquidity mining returns factor in the reward payments vs. order volumes only.  They *do not* capture the individual miner's return on the underlying strategy or any transaction fees (if any) that generated the orders created.  As a result, *liquidity mining returns are not an indication of a miner's overall portfolio return*; miners should take into consideration overall economics, and not just mining return, when deciding on participating in liquidity mining campaigns.

!!! warning "Liquidity mining return is a historic metric and not a guarantee of future return."
    The liquidity mining return displayed on the Hummingbot Miner app is calculated from the most recently collected order book information data.  The actual return may vary depending on the actual orders submitted in the specific snapshot in which orders were placed.

For more details on the calculation, please read [Demystifying Liquidity Mining Rewards](https://hummingbot.io/blog/2019-12-liquidity-mining-rewards/).

### How are the reward allocated for each order book snapshot?
In each weekly epoch, the lump-sum weekly reward is distributed equally across each minute within that epoch.  For each minute, a random snapshot is taken from within that minute to be used for calculating reward allocations.

For each snapshot, half the reward is allocated to the bid-side of the order book, and the other half is allocated to the ask side of the order book. We mandate this 50/50 split in order to deter participants from using our system to manipulate price in one direction or another. If there are no eligible orders submitted for a specific snapshot, the amount of rewards allocated for that snapshot will roll over and be added to the reward amount for the subsequent snapshot.

### Do my earnings in one market affect other markets?
No, reward allocations for each market are calculated independently. Each payment distribution will be based on qualifying activity in the immediately preceding weekly epoch, and not on prior epochs.

### When are liquidity mining rewards paid out?
Each weekly epoch runs begins and ends at Tuesday 12am UTC. Rewards are distributed to each participant's registered Ethereum address 3 calendar days after the end of each epoch.

### How do you measure and verify the liquidity that I provide?
In order to accurately measure liquidity and allocate rewards, miners need to provide a working read-only API key for each exchange where they want to earn rewards. Our data infrastructure uses read-only API keys to collect and aggregate order data for each miner.

In addition, we run proprietary algorithms in order to attempt any prohibited actions such as wash trading and spoofing. While exploitative practices can be difficult to identify given the adversarial nature of the market, we believe that the combination of our focus on compliance, granular data feeds, and machine learning-based algorithms may deter and detect bad actors.

### Do you store data that you collect with my read-only API keys?
At launch, we store individual orders and trades in order to isolate and prevent potential attempts to manipulate or abuse the system by malicious liquidity miners. After the system is more mature, we will adjust the data collection process so that we only store aggregate data and do not store individual orders and trades. We never share individual order and trade data with third parties.

### What risks does a liquidity miner bear?
Like any trading strategy, market making includes risk. One of the primary risks is **inventory risk**, the risk of negative changes in inventory value as a result of market making. For instance, if prices drop significantly in a short time period and a market maker accumulates a large position in the asset due to continual fills of their market maker's buy orders, their overall inventory value may be lower.

Note that published liquidity mining returns illustrate the return from liquidity rewards proportional to the value of the inventory committed to maintain orders. These figures do not take into account trading-related profits and losses.  The return figures may also fluctuate based on relative changes in the value of the base tokens, quote tokens, and the tokens used for the liquidity mining payments.

### How is Hummingbot compensated for liquidity mining programs?
In return for administering liquidity mining programs, collecting the data necessary to verify the trading activity of participants, and automating the payout process, we receive compensation from our Liquidity Mining partners and customers.

### Do I need to use the Hummingbot client to participate in liquidity mining?
No; if you already have your own trading bots and strategies, you can still participate in liquidity mining by registering.  

For the general pool of users who don't have their own trading bots, we created Hummingbot as a way to provide them access to quant/algo strategies and the ability to market make.

## Common Support Questions

Below are frequently asked questions that we get from users.

### I’m running on pure market making strategy. Why is it only placing buy orders and not sell orders? (or vice-versa)

Check the balance in your inventory. If you don't have enough balance on one side, it will only place orders on the side that it can. This is fine and expected behavior for the strategy.


### What settings or parameter values should I use to make profitable trades?

Hummingbot does not advise on parameter values. As a market maker, testing different parameters and seeing how they perform is really the art or science of market making.


### Where can I submit a feature/feedback request?
1. You can create a feature request through this [link](https://github.com/CoinAlpha/hummingbot/issues).
2. Select the green button **new issue**.
3. Choose **feature request** then fill it accordingly.


### Where are the config and log files on Hummingbot installed via Docker?

Run the following command to view the details of your instance:

```bash
docker inspect $instance_name
```

Look for a field `Mounts`, which will describe where the folders are on you local machine:

```
"Mounts": [
    {
        "Type": "bind",
        "Source": "/home/ubuntu/hummingbot_files/hummingbot_data",
        "Destination": "/data",
        "Mode": "",
        "RW": true,
        "Propagation": "rprivate"
    },
    {
        "Type": "bind",
        "Source": "/home/ubuntu/hummingbot_files/hummingbot_conf",
        "Destination": "/conf",
        "Mode": "",
        "RW": true,
        "Propagation": "rprivate"
    },
    {
        "Type": "bind",
        "Source": "/home/ubuntu/hummingbot_files/hummingbot_logs",
        "Destination": "/logs",
        "Mode": "",
        "RW": true,
        "Propagation": "rprivate"
    }
],
```

!!! note
    Read through [Log File Management](https://docs.hummingbot.io/utilities/logging/) for more information.


### How to edit the conf files or access the log files used by my docker instance?

If Hummingbot is installed on a virtual machine or a Linux cloud server, you can use the `vi` text editor (or any text editor of your choice). Run command `vi $filename`. See [this page](https://www.tipsandtricks-hq.com/unix-vi-commands-take-advantage-of-the-unix-vi-editor-374) for more information how to use this text editor.

You can also use an FTP client software (e.g. WinSCP, FileZila) to copy, move, files and folders from your virtual machine to your local machine and vice versa.


### Paste items from clipboard in PuTTY

You should be able to paste items from your clipboard by doing mouse right-click or `SHIFT + right-click`. If that doesn't work, follow the steps below.

1. If you are currently logged in a session, left-click on the upper left hand corner of the PuTTY window or a right-click anywhere on the title bar then select "Change Settings". If not, proceed to next step.
2. In PuTTY configuration under Window category go to "Selection". Select the "Window" radio button for action of mouse buttons.
3. You can now paste items from clipboard by doing a right-click to bring up the menu and select "Paste".

![](/assets/img/putty_copy_paste.gif)


### Other ways to copy and paste

Copying to clipboard on Windows or Linux:

```
Ctrl + C 
Ctrl + Insert
Ctrl + Shift + C
```

Pasting items from clipboard on Windows or Linux:

```
Ctrl + V
Shift + Insert
Ctrl + Shift + V
```


### Locate data folder or hummingbot_trades.sqlite when running Hummingbot via Docker

1. Find ID of your running container.
```
# Display list of containers
docker container ps -a

# Start a docker container
docker container start <PID>
```
2. Evaluate containers file system.
```
run docker exec -t -i <name of your container> /bin/bash
```
3. Show list using `ls` command.
4. Switch to `data` folder and use `ls` command to display content.
5. If you would like to remove the sqlite database, use `rm <database_name>` command.

In version 0.22.0 release, we updated the Docker scripts to map the `data` folder when creating and updating an instance.

1. Delete the old scripts.
```
rm create.sh update.sh
```
2. Download the updated scripts.
```
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh
```
3. Enable script permissions.
```
chmod a+x *.sh
```
4. Command `./create.sh` creates a new Hummingbot instance.
5. Command `./update.sh` updates an existing Hummingbot instance.


### Get REST API data using Postman

Some information related to an exchange can be retrieved through their public API such as minimum order sizes. You can download a program called [Postman](https://www.getpostman.com/) and follow the instructions in [Get Started with Postman](https://learning.getpostman.com/getting-started/).

![](/assets/img/postman.png)


### How to reset in case of forgotten password

For security reasons, Hummingbot does not store your password anywhere so there's no way to recover it. The only solution is to create a new password and re-enter your API keys upon restarting Hummingbot after deleting or moving the encrypted files.

1. Run `exit` command to exit from the Hummingbot client.
2. Delete the encrypted files and wallet key file (if applicable) from the `hummingbot_conf` folder.
3. Restart Hummingbot and run `config` command.

If using Linux, copy the commands below and run in your terminal to delete the files. You will be prompted to confirm before proceeding.

```bash tab="Docker build"
rm hummingbot_files/hummingbot_conf/encrypted* hummingbot_files/hummingbot_conf/key_file*
```

```bash tab="Source build"
rm hummingbot/conf/encrypted* hummingbot/conf/key_file*
```

If Hummingbot is installed on Windows, simply delete the encrypted files found in `%localappdata%\hummingbot.io\Hummingbot\conf`.

!!! warning
    Be careful when deleting the local wallet key file created through Hummingbot, i.e, a wallet that was not imported from Metamask; deleting the key file will result in a permanent loss of access to that wallet and any assets it may contain.

![delete_encrypted_files](/assets/img/ts_delete_encrypted.gif)


### Transfer files from/to Windows Subsystem for Linux and local computer
1. Execute command `explorer.exe .` (make sure to include the dot) in WSL to launch a file explorer window of your current directory. Then you will be able to move, copy and delete files like you normally would on a Windows computer.
2. If command `explorer.exe .` fails to open your hummingbot directory, you need to [disable and enable WSL using powershell](https://www.tenforums.com/tutorials/46769-enable-disable-windows-subsystem-linux-wsl-windows-10-a.html)


### Download a previous version of Hummingbot in Windows

1. Go to `https://hummingbot-distribution.s3.amazonaws.com/`. It will show an XML file with all the Hummingbot versions listed.</br></br>
    ![binary_distribution](/assets/img/ts_binary_distribution.png)</br></br>
2. To download a previous version, add the version inside `<Key>` after the URL.

For example, enter the URL</br>
https://hummingbot-distribution.s3.amazonaws.com/hummingbot_v0.20.0_setup.exe
</br>on your web browser to start downloading the installer for Hummingbot version 0.20.0.


### Alternate method to locate Hummingbot data files if you use a binary installer

#### Windows Computer

1. Open File Explorer, select This PC and open local disc (C:\)
2. Browse to the Users folder, and open your profile folder.
3. Locate and open **AppData** folder
4. Open **Local** folder then **Hummingbot.io** folder. You may see another folder named **Hummingbot**, open it and you will see the data files folder.

!!! tip
    In case the AppData folder is not visible, on the menu bar found above your folder, go to **View** and tick the checkbox for Hidden items.
	 
#### Mac Computer

1. Open Finder
2. On the top menu bar, click **Go**
3. After clicking the **Go** menu, press the Option button on your keyboard.
4. Additional **Library** option should appear after that. 
5. Click **Library** 
6. Find and open **Application Support** folder and you will see **Hummingbot** folder.

!!! note
    Mac has multiple library folders, make sure that the library folder you're trying to open is the Library folder under your user profile.
 

### How to check the status of multiple bot simultaneously?
1. As of the moment, you can only check the status of each bot one at a time. 
2. A workaround is to integrate telegram on all your hummingbot instances and use a single telegram_chat_ID.

!!! note
    Read through [Telegram integration](https://docs.hummingbot.io/utilities/telegram/) for more information.


### How to add paper trade balance settings inside Hummingbot CLI?
1. Stop the bot first if its running since parameter is part of the global settings
2. Type in `config paper_trade_account_balance`
3. Enter the token symbol and amount with the same format given on the input window. </br>
    ![cli_add_balance](/assets/img/cli_add_balance.gif)</br>
4. Press Enter to add and save the new token symbol.

!!! note
    1. Adding a new token balance should be done upon starting your bot (before importing or creating strategy) to avoid error.
    2. Default paper_trade tokens and amounts will be removed upon adding a new token pair. Don't forget to add all the tokens you need.


### How to refresh Hummingbot Window Panes?
When resizing the window of your Hummingbot, text becomes unclear or at the same location as the previous size of the window. To do a refresh to the new window size, while inside Hummingbot press `CTRL + L` and it will refresh Hummingbot window panes. These command applies to all Hummingbot build.
