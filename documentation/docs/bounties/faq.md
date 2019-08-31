# Liquidity Bounties FAQ

## What are liquidity bounties?
Liquidity bounties are a community-based approach to market making. Inspired by bug bounties, liquidity bounties allow Hummingbot users to **earn rewards by market making** for specific tokens and/or trading pairs. 

For more information, please see the blog post [Introducing Liquidity Bounties](https://www.hummingbot.io/blog/2019-06-introducing-liquidity-bounties-harmony/).

## What is market making?
Market making is a strategy that allows traders to earn profits by providing liquidity to a market. They do so by creating and maintaining limit orders to buy and sell an asset. 

By setting buy prices lower than sell prices, market makers earn profits via the **bid-ask spread** (the distance between buy prices and sell prices).  

## What is liquidity?
Liquidity is necessary for any publicly traded asset. In a market, buyers and sellers want to transact at a fair price in a deep, orderly market with little slippage. Liquidity is very important primarily for the following reasons:

First and foremost, it impacts how easily and quickly one can buy and/or sell an asset in the market. In a liquid market, buyers won’t have to pay an increased price to secure the assets they want. On the other hand, sellers will quickly find buyers at the set price without having to cut it down to attract buyers.

Second, higher liquidity is generally associated with less risk and higher market efficiency. A liquid market tends to attract more traders, investors and holders. This contributes to the favorable market conditions and forms a virtuous cycle. More participants, better liquidity.

There are a few commonly-used indicators of liquidity. Primary ones include tight bid-ask spreads, deep order books, and real, active trading volume.

## Why is market making important in crypto?
<a href="https://en.wikipedia.org/wiki/Market_maker" target="_blank">Market makers</a> play an important role in providing liquidity in a trade, especially in the cryptocurrency world. In the traditional financial world, liquidity providers(i.e. **market makers**) are dominated by highly technical quantitative hedge funds and trading firms who have the infrastructure and intelligence to deploy sophisticated algorithms at scale.

Liquidity is an even bigger issue in the fragmented world of crypto. While large professional market makers fight over the most actively traded pairs on the highest volume exchanges, there exists a massive **long tail of smaller markets** who also need liquidity: tokens outside the top 10, smaller exchanges, decentralized exchanges, and new blockchains. 

In addition, the prohibitively high payment demanded by pro market makers, coupled with lack of transparency and industry standards, creates perverse incentives for certain bad players to act maliciously via wash trading and market manipulation.

For more discussion on the liquidity problem, please check out [this blog post](https://www.hummingbot.io/blog/2019-01-thin-crust-of-liquidity/).

## What strategies can a market maker use?
Professional market makers utilize many different strategies, ranging from simple to sophisticated. We have implemented two basic strategy templates:

- [Pure market making (market making on a single exchange)](https://docs.hummingbot.io/strategies/pure-market-making/)
- [Cross-exchange market making](https://docs.hummingbot.io/strategies/cross-exchange-market-making/)


## What risks does a market maker bear?
Like any trading strategy, market making includes risk. One of the primary risks is **inventory risk**, the risk of negative changes in inventory value as a result of market making. For instance, if prices drop significantly in a short time period and a market maker accumulates a large position in the asset due to continual fills of their market maker's buy orders, their overall inventory value may be lower.

## How do you verify that liquidity bounty trading volume is Real?
We take compliance extremely seriously, because we want to reward only genuine providers of liquidity. For this reason, participants need to opt into data collection, which allows us to attempt to verify their trading activity against our internal exchange data feeds in order to prevent reporting of fake volume. 

In addition, we will run proprietary algorithms in order to attempt to detect wash trading and spoofing. While exploitative practices can be difficult to identify given the adversarial nature of the market, we believe that the combination of our focus on compliance, granular data feeds, and machine learning-based algorithms may deter and detect bad actors.

## How is Hummingbot compensated for liquidity bounties?
In return for administering a Liquidity Bounty, collecting the data necessary to verify the trading activity of participants, and automating the payout process, we receive a percentage of the total payouts from our other Liquidity Bounty partners.
