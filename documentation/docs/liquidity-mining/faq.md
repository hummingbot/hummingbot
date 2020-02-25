# Liquidity Mining FAQ

!!! info "Important Disclaimer"
    <small><ul><li>The content of this Site does not constitute investment, financial, legal, or tax advice, nor does any of the information contained on this Site constitute a recommendation, solicitation, or offer to buy or sell any digital assets, securities, options, or other financial instruments or other assets, or to provide any investment advice or service.<li>There is no guarantee of profit for participating in liquidity mining.<li>Participation is subject to eligiblity requirements.</ul></small>
    **Please review the [Liquidity Mining Policy](https://hummingbot.io/liquidity-mining-policy/) for the full disclaimer.**

## General

### What is liquidity?
Liquidity is necessary for any publicly traded asset. In a market, buyers and sellers want to transact at a fair price in a deep, orderly market with little slippage. Liquidity is very important primarily for the following reasons:

First and foremost, it impacts how easily and quickly one can buy and/or sell an asset in the market. In a liquid market, buyers won’t have to pay an increased price to secure the assets they want. On the other hand, sellers will quickly find buyers at the set price without having to cut it down to attract buyers.

Second, higher liquidity is generally associated with less risk and higher market efficiency. A liquid market tends to attract more traders, investors and holders. This contributes to the favorable market conditions and forms a virtuous cycle. More participants, better liquidity.

There are a few commonly-used indicators of liquidity. Primary ones include tight bid-ask spreads, deep order books, and real, active trading volume.

### What is market making?
Market making is the act of simultaneously creating buy and sell orders for an asset in a market.  By doing so, a market maker acts as a liquidity provider, facilitating other market participants to trade by giving them the ability to fill the market maker's orders.

Market makers set buy prices lower than sell prices (the difference in prices being the "bid-ask spread") and aim to profit by capturing this bid-ask spread over time.

### Why is market making important in crypto?
<a href="https://en.wikipedia.org/wiki/Market_maker" target="_blank">Market makers</a> play an important role in providing liquidity in a trade, especially in the cryptocurrency world. In the traditional financial world, liquidity providers(i.e. **market makers**) are dominated by highly technical quantitative hedge funds and trading firms who have the infrastructure and intelligence to deploy sophisticated algorithms at scale.

Liquidity is an even bigger issue in the fragmented world of crypto. While large professional market makers fight over the most actively traded pairs on the highest volume exchanges, there exists a massive **long tail of smaller markets** who also need liquidity: tokens outside the top 10, smaller exchanges, decentralized exchanges, and new blockchains.

In addition, the prohibitively high payment demanded by pro market makers, coupled with lack of transparency and industry standards, creates perverse incentives for certain bad players to act maliciously via wash trading and market manipulation.

For more discussion on the liquidity problem, please check out [this blog post](https://www.hummingbot.io/blog/2019-01-thin-crust-of-liquidity/).

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

## Hummingbot Miners Dashboard

### What are the tabs on the dashboard?

Tab | Description
---|---
**Markets** | Displays the currently available liquidity mining campaigns: eligible token pairs, exchanges, and recent participation and reward metrics
**Activity** | Displays a miner's currently accrued rewards, recent history of rewards earned, as well as payout history.
**Settings** | Configuration tab for setting up exchange APIs to enable participation in liquidity mining campaigns.

### What do the figures on the Markets tab mean?

The figures on the Markets tab show a summary of aggregated data across all campaigns and across all miners, as well as aggregated data for each token pair.

![](../assets/img/hummingbot-miners-dashboard.png)

<small><em>Note: figures above are for illustration only and do not represent current campaign terms; navigate to [Hummingbot Miners](https://miners.hummingbot.io) for current campaign details.</em></small>

### Why do I need to connect my wallet?

![](../assets/img/hummingbot-miners-connect_wallet.png)

<small><em>Note: figures above are for illustration only and do not represent current campaign terms; navigate to [Hummingbot Miners](https://miners.hummingbot.io) for current campaign details.</em></small>

The Hummingbot Miners app uses your Ethereum wallet address for:

1. **assigning you a unique user ID**.  The Hummingbot miners app associates your configurations (e.g. email address, API configurations), as well as activity.  This allows the miners app to display your user-specific information such as rewards earned and payout history.
2. **payouts**: mining rewards payouts will be sent to this address

!!! note "Wallet not used for trading"
    Since it is only used for the purposes mentioned above, you do not need deposit assets into or trade using this wallet.

## Reward Calculations

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

For each snapshot, half the reward is allocated to the bid-side of the order book, and the other half is allocated to the ask side of the order book. We mandate this 50/50 split in order to deter participants from using our system to manipulate price in one direction or another.

### What happens if there are no orders from liquidity miners in a given order book snapshot?
If there are no eligible orders submitted for a specific snapshot, the amount of rewards allocated for that snapshot will roll over and be added to the reward amount for the subsequent snapshot.

### Do my earnings in one market affect other markets?
No, reward allocations for each market are calculated independently. Each payment distribution will be based on qualifying activity in the immediately preceding weekly epoch, and not on prior epochs.

## Reward Payouts

### When are liquidity mining rewards paid out?
Each weekly epoch runs begins and ends at Tuesday 12am UTC. Rewards are distributed to each participant's registered Ethereum address 3 calendar days after the end of each epoch.

## Compliance and Data Storage

### How do you verify the trading activities?
We take compliance extremely seriously, and aim to only reward genuine providers of liquidity. For this reason, participants need to opt into data collection and provide their read-only API keys for exchanges, in order to allow us to verify trading activity. In addition, we run proprietary algorithms in order to attempt any prohibited actions such as wash trading and spoofing. While exploitative practices can be difficult to identify given the adversarial nature of the market, we believe that the combination of our focus on compliance, granular data feeds, and machine learning-based algorithms may deter and detect bad actors.

### Why do you need my read-only API keys? 
In order to accurately allocate rewards, we need to separate individual miner orders from one another. Our data infrastructure uses read-only API keys to collect and aggregate order data for each miner. 

### Do you store data that you collect with my read-only API keys?
At launch, we store individual orders and trades in order to isolate and prevent potential attempts to manipulate or abuse the system by malicious liquidity miners. After the system is more mature, we will adjust the data collection process so that we only store aggregate data and do not store individual orders and trades. We never share individual order and trade data with third parties.

## Miscellaneous

### What risks does a liquidity miner bear?
Like any trading strategy, market making includes risk. One of the primary risks is **inventory risk**, the risk of negative changes in inventory value as a result of market making. For instance, if prices drop significantly in a short time period and a market maker accumulates a large position in the asset due to continual fills of their market maker's buy orders, their overall inventory value may be lower.

Note that published liquidity mining returns illustrate the return from liquidity rewards proportional to the value of the inventory committed to maintain orders. These figures do not take into account trading-related profits and losses.  The return figures may also fluctuate based on relative changes in the value of the base tokens, quote tokens, and the tokens used for the liquidity mining payments.

### How is Hummingbot compensated for liquidity mining programs?
In return for administering liquidity mining programs, collecting the data necessary to verify the trading activity of participants, and automating the payout process, we receive compensation from our Liquidity Mining partners and customers.

### How are liquidity miners compensated in liquidity mining programs?
From the fees that Hummingbot receives from its partners and customers, Hummingbot allocates a portion to pay miners for participating and sharing their trading data.  The amount of liquidity payments that Hummingbot makes to miners is based on the terms specified in each liquidity mining campaign, referencing a miner's orders created and their spreads and sizes.

### Do I need to use the Hummingbot client to participate in liquidity mining?
No; if you already have your own trading bots and strategies, you can still participate in liquidity mining by registering.  

For the general pool of users who don't have their own trading bots, we created Hummingbot as a way to provide them access to quant/algo strategies and the ability to market make.
