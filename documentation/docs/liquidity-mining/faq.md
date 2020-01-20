# Liquidity Mining FAQ

## What is liquidity mining?
Liquidity mining is a community-based approach to market making. It means the collective actions of a pool of decentralized users ("liquidity miners") that provide computing resources as well as their own exchange accounts, wallets, and digital assets to provide liquidity for a digital asset or a set of digital assets and to **earn rewards by market making**.

For more information, please read [the whitepaper](https://hummingbot.io/liquidity-mining.pdf).

## What is market making?
Market making is a strategy that allows traders to earn profits by providing liquidity to a market. They do so by creating and maintaining limit orders to buy and sell an asset.

By setting buy prices lower than sell prices, market makers earn profits via the **bid-ask spread** (the distance between buy prices and sell prices).  

## What is liquidity?
Liquidity is necessary for any publicly traded asset. In a market, buyers and sellers want to transact at a fair price in a deep, orderly market with little slippage. Liquidity is very important primarily for the following reasons:

First and foremost, it impacts how easily and quickly one can buy and/or sell an asset in the market. In a liquid market, buyers won’t have to pay an increased price to secure the assets they want. On the other hand, sellers will quickly find buyers at the set price without having to cut it down to attract buyers.

Second, higher liquidity is generally associated with less risk and higher market efficiency. A liquid market tends to attract more traders, investors and holders. This contributes to the favorable market conditions and forms a virtuous cycle. More participants, better liquidity.

There are a few commonly-used indicators of liquidity. Primary ones include tight bid-ask spreads, deep order books, and real, active trading volume.

## How to measure liquidity?
To measure liquidity, we use **slippage**, which measures the price impact of a buy or sell order. Slippage refers to the difference between the expected price of a trade and the price at which the trade is actually executed. Deep, liquid order books have low slippage, while thin, illiquid order books have high slippage.

**We believe slippage is a more robust indicator of liquidity than trading volume**. As an ex-ante metric, slippage measures information used by traders before they trade to decide whether to execute the trade and in which venue to execute it. In contrast, volume is an ex-post metric and can be easily manipulated.

## Why is market making important in crypto?
<a href="https://en.wikipedia.org/wiki/Market_maker" target="_blank">Market makers</a> play an important role in providing liquidity in a trade, especially in the cryptocurrency world. In the traditional financial world, liquidity providers(i.e. **market makers**) are dominated by highly technical quantitative hedge funds and trading firms who have the infrastructure and intelligence to deploy sophisticated algorithms at scale.

Liquidity is an even bigger issue in the fragmented world of crypto. While large professional market makers fight over the most actively traded pairs on the highest volume exchanges, there exists a massive **long tail of smaller markets** who also need liquidity: tokens outside the top 10, smaller exchanges, decentralized exchanges, and new blockchains.

In addition, the prohibitively high payment demanded by pro market makers, coupled with lack of transparency and industry standards, creates perverse incentives for certain bad players to act maliciously via wash trading and market manipulation.

For more discussion on the liquidity problem, please check out [this blog post](https://www.hummingbot.io/blog/2019-01-thin-crust-of-liquidity/).

## What strategies can a liquidity miner use?
Professional market makers utilize many different strategies, ranging from simple to sophisticated. We have implemented two basic strategy templates:

- [Pure market making (market making on a single exchange)](https://docs.hummingbot.io/strategies/pure-market-making/)
- [Cross-exchange market making](https://docs.hummingbot.io/strategies/cross-exchange-market-making/)

If you want to participate in liquidity mining programs, please choose the above two strategies for trading in order to earn rewards. 

## What risks does a liquidity miner bear?
Like any trading strategy, market making includes risk. One of the primary risks is **inventory risk**, the risk of negative changes in inventory value as a result of market making. For instance, if prices drop significantly in a short time period and a market maker accumulates a large position in the asset due to continual fills of their market maker's buy orders, their overall inventory value may be lower.

## How do you determine liquidity miners' rewards?
In order to make economic sense for a market maker, the market maker’s compensation must correlate with increased levels of risk. There are three main parameters that we use in liquidity mining to determine market maker compensation: (1) **time**: placing orders in the order book consistently over time, (2) **spreads**, and (3) **order sizes**. Our rewards methodology rewards market makers more for placing orders consistently over time in the order book, placing orders with tighter spreads and with larger sizes as shown in the below figure. The real-time reward information will be displayed in the real-time user dashboard. 
![](https://hummingbot.io/static/e9bcf5a0b0ad5320f95f0a1de89c3e9a/ed7b0/rewards-allocation-chart.png)

For more details on the calculation, please read [Demystifying Liquidity Mining Rewards](https://hummingbot.io/blog/2019-12-liquidity-mining-rewards/). 

## How do you verify the trading activities?
We take compliance extremely seriously, and only reward genuine providers of liquidity. For this reason, participants need to opt into data collection and provide their read-only API keys for exchanges, in order to allow us to verify trading activity. In addition, we run proprietary algorithms in order to attempt any prohibited actions such as wash trading and spoofing. While exploitative practices can be difficult to identify given the adversarial nature of the market, we believe that the combination of our focus on compliance, granular data feeds, and machine learning-based algorithms may deter and detect bad actors.

## How is Hummingbot compensated for liquidity mining programs?
In return for administering liquidity mining programs, collecting the data necessary to verify the trading activity of participants, and automating the payout process, we receive a percentage of the total payouts from our other Liquidity Mining partners.
