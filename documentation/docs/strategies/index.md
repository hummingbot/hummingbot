# Strategies

The current release of Hummingbot comes with four strategies. Click on the strategy name for more information.

| Strategy | Description |
|----|----|
| **[Arbitrage](/strategies/arbitrage)** | Aims to capture price differentials between two different exchanges (buy low on one, sell high on the other). <br/><br/>*This strategy aims to minimize risk (minimal incremental risk vs. owning tokens, or "inventory risk"), making it a good starting point for users wanting to try out Hummingbot.* |
| **[Cross Exchange Market Making](/strategies/cross-exchange-market-making)** | Also referred to as *liquidity mirroring* or *exchange remarketing*.  In this strategy, Hummingbot makes markets (creates buy and sell orders) on smaller or less liquid exchanges and does the opposite, back-to-back transaction for any filled trades on a more liquid exchange.  <br/><br/>*This strategy carries a similar risk as arbitrage and similar setup.* |
| **[Pure Market Making](/strategies/pure-market-making)** | Post buy and sell offers for an instrument on a single exchange, automatically adjust prices while actively managing inventory. <br/><br/>*This strategy has a relatively higher risk and complexity as compared to other strategies and we ask users to exercise caution and understand it completely before running it.* |
| **[Discovery](/strategies/discovery)** | A preliminary strategy that assists in identifying trading opportunities by examining different specified pairs across denoted exchanges and ranking them according to profitability. <br/><br/>*This strategy is for informational purposes only and does not result in actual trading.* |

The [Hummingbot whitepaper](https://www.hummingbot.io/whitepaper.pdf) provides more details about these strategies, as well as additional ones that we are working on for future versions of Hummingbot.

!!! note
    These strategies are meant to be basic templates. We encourage users to extend these templates for their own purposes, and if they so desire, share them with the community.<br /><br />For developers interested to create their own strategies, please see [Developers: Strategies](/developers/strategies).

<br />
