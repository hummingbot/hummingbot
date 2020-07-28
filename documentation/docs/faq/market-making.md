# Market Making FAQs

### What is market making?
Market making is the act of simultaneously creating buy and sell orders for an asset in a market. By doing so, a market maker acts as a liquidity provider, facilitating other market participants to trade by giving them the ability to fill the market maker's orders. Traditionally, market making industry has been dominated by highly technical quantitative hedge funds and trading firms who have the infrastructure and intelligence to deploy sophisticated algorithms at scale.

Market makers play an important role in providing liquidity to financial markets, especially in the highly fragmented cryptocurrency industry. While large professional market makers fight over the most actively traded pairs on the highest volume exchanges, there exists a massive **long tail of smaller markets** who also need liquidity: tokens outside the top 10, smaller exchanges, decentralized exchanges, and new blockchains.

In addition, the prohibitively high payment demanded by pro market makers, coupled with lack of transparency and industry standards, creates perverse incentives for certain bad players to act maliciously via wash trading and market manipulation. For more discussion on the liquidity problem, please check out [this blog post](https://www.hummingbot.io/blog/2019-01-thin-crust-of-liquidity/).


## How does market making work?

!!! warning
    Not financial or investment advice.  Below are descriptions of some risks associated with the pure market making strategy.  There may be additional risks not described below.

### Ideal case

Market making strategies works best when you have a market that's relatively calm, but with sufficient trading activity. What that means for a pure market makers is, he would be able to get both of his bid and ask offers traded regularly; the price of his inventory doesn't change by a lot so there's no risk of him ending up on the wrong side of a trend. Thus he would be able to repeatedly capture small profits via the bid/ask spread over time.

![Figure 2: A clam market with regular trading activity](/assets/img/pure-mm-calm.png)

In the figure above, the period between 25 Feb and 12 Mar would be an example of the ideal case. The price of the asset stayed within a relatively small range, and there was sufficient trading activity for a market maker's offers to be taken regularly.

The only thing a market maker needs to worry about in this scenario is he must make sure the trading spread he sets is larger than the trading fees given to the exchange.

### Low trading activity

Markets with low trading activity higher risk for pure market making strategies. Here's an example:

![Figure 3: A market with low trading activity](/assets/img/pure-mm-low-volume.png)

In any market with low trading activity, there's a risk where the market maker may need to hold onto inventory for a long time without a chance to trade it back. During that time, the prices of the traded assets may rise or drop dramatically despite seeing no or little trading activity on the exchange. This exposes the market maker to inventory risk, even after mitigating some of this risk by using wider bid spreads.

Other strategies may be more suitable from a risk perspective in this type of market, e.g. [cross-exchange market making](/strategies/cross-exchange-market-making).

### Market/inventory risk due to low volatile or trending markets

Another common risk that market makers need to be aware of is trending markets. Here's one example:

![Figure 4: A trending market](/assets/img/pure-mm-trending.png)

If a pure market maker set his spreads naively in such a market, e.g. equidistant bid/ask spread, there's a risk of the market maker's bid consistently being filled as prices trend down, while at the same time the market continues to move away from the market maker's ask, decreasing the probability of sells.  This would result in an accumulation of inventory at exactly the time where this would reduce inventory inventory value, which is "wrong-way" risk.

However, it is still possible to improve the probability of generating profits in this kind of market by skewing bid asks, i.e. setting a wider bid spread (e.g. -4%) than ask spread (e.g. +0.5%).  In this way, the market maker is trying to catch price spikes in the direction of the trend and buy additional inventory only in the event of a larger moves, but sell more quickly when there is an opportunity so as to minimize the duration the inventory is held.  This approach also has a mean reversion bias, i.e. buy only when there is a larger move downwards, in the hopes of stabilization or recovery after such a large move.

Market making in volatile or trending markets is more advanced and risky for new traders. It's recommended that a trader looking to market make in this kind of environment to get mentally familiar with it (e.g. via paper trading) before committing meaningful capital to the strategy.

## Besides market risk, what other risks does a market maker face?

There are many moving parts when operating a market making bot that all have to work together in order to properly function:

- Hummingbot code
- Exchange APIs
- Ethereum blockchain and node
- Network connectivity
- Hummingbot host computer

A fault in any component may result in bot errors, which can range from minor and inconsequential to major.

It is essential for any market making bot to be able to regularly refresh its bid and ask offers on the market in order to adjust to changing market conditions.  If a market making bot is disconnected from the exchange for an extended period of time, then the bid/ask offers it previously made would be left on the market and subject to price fluctuations of the market. Those orders may be filled at a loss as market prices move, while the market maker is offline.  It is very important for any market maker to make sure technical infrastructure is secure and reliable.

## Market making terminology
Market making, along with algorithmic trading generally, uses industry-specific terminology. We define some of the most commonly used terms below.

| Term | Definition |
|------|------------|
| **base asset** | The asset in a trading pair whose quantity is fixed as a single unit in a price quote. For example, in a price quotation of ETH/DAI 100, ETH is the **base asset** and 100 is the amount of DAI exchangeable for each unit of ETH.<br/><br/>In Hummingbot, the first token in a trading pair is always the base asset. See **quote asset** for more info.
| **centralized exchange (“CEX”)** | An exchange which is operated by a central authority.  In addition to order matching and broadcasting, the centralized exchange keeps custody of users’ assets.
| **decentralized exchange (“DEX”)** | An exchange which operates in a decentralized way, using smart contracts to facilitate the transacting in and settling of assets. Generally, one distinguishing feature of a decentralized exchange is that participants keep custody of their own assets in their own wallets; the DEX facilitates the direct wallet-to-wallet settlement between counterparties in a transaction.
| **maker** | A party that places _maker orders_, and in doing so, provides liquidity to the market.
| **maker order** | A “limit order”; which is an order to buy or sell an asset at a specified price and quantity.  Execution of this order is not guaranteed; the order is only filled if there is a taker that accepts the price and quantity and transacts.
| **order book** | A list of currently available (maker) orders on an exchange, showing all of the current buyer and seller interest in an asset.
| **quote asset** | The asset in a asset pair whose quantity varies and whose quantity is denoted by the numerical figure of the price quote. For example, in a price quotation of ETH/DAI 100, DAI is the quote currency and 100 units of DAI are referenced in this exchange.<br/><br/>In Hummingbot, the second token in a trading pair is always the quote asset. See **base asset** for more info.
| **taker** | A party that places _taker orders_, which execute immediately and fill a maker order.
| **taker order** | A “market order”; an order to buy or sell a specified quantity of an asset which is filled immediately at the best available price(s) available on the exchange.
| **mid price** | The average of best bid and best ask price in the orderbook.
| **hedging price** | In cross exchange strategy, is the net cost of the other side of your limit order i.e., the cost of you making a taker order.<br/><br/>*For example on your taker market, if you can buy 25 tokens for say a net price of $100 (other market makers have limit sell orders at a net price of 100 for all 25, e.g. 7.5 @ $99, 10 @ $100, 7.5 @ $101), then on your maker side, you would place a limit sell order for 25 @ $101 (assume 1% min profitability). If someone fills your sell order (you sell at $101), you immediately try to hedge by buying on the taker side at $100.*