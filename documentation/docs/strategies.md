# Strategies

The current release of Hummingbot comes with two strategies. Click on the strategy name for more information about it.

| Strategy | Description |
|----|----|
| **[Arbitrage](/strategies/arbitrage)** | Aims to capture price differentials between two different exchanges (buy low on one, sell high on the other). |
| **[Cross exchange market making](/strategies/cross-exchange-market-making)** | Also referred to as *liquidity mirroring* or *exchange remarketing*.  In this strategy, Hummingbot makes markets (creates buy and sell orders) on smaller or less liquid exchanges and does the opposite, back-to-back transaction any filled trades on a more liquid exchange.  <br/><br/>*This strategy has relatively lower risk and complexity as compared to other market making strategies, which we thought would be a good starting point for initial users.* |
| **[Pure market making](/strategies/pure-market-making)** | Post buy and sell offers for an instrument on a single exchange, automatically adjust prices while actively managing inventory. <br/><br/>*This strategy has a relatively higher risk and complexity as compared to other strategies and we ask users to exercise caution and understand it completely before running it.* |

The [Hummingbot whitepaper](https://www.hummingbot.io/whitepaper.pdf) provides more details about these strategies, as well as additional strategies that we are working on for future versions of Hummingbot.

!!! note
    These strategies are meant to be basic templates. We encourage users to extend these templates for their own purposes, and if they so desire, share them with the community.

