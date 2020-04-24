# Strategies

The current release of Hummingbot comes with four strategies:

## [Pure Market Making](/strategies/pure-market-making)

Post buy and sell offers for an instrument on a single exchange, automatically adjust prices while actively managing inventory.

## [Cross Exchange Market Making](/strategies/cross-exchange-market-making)

Also referred to as *liquidity mirroring* or *exchange remarketing*.  In this strategy, Hummingbot makes markets (creates buy and sell orders) on smaller or less liquid exchanges and does the opposite, back-to-back transaction for any filled trades on a more liquid exchange.

## [Arbitrage](/strategies/arbitrage)

Aims to capture price differentials between two different exchanges (buy low on one, sell high on the other).

---

The [Hummingbot whitepaper](https://www.hummingbot.io/hummingbot.pdf) provides more details about these strategies, as well as additional ones that we are working on for future versions of Hummingbot.

!!! note
    These strategies are meant to be basic templates. We encourage users to extend these templates for their own purposes, and if they so desire, share them with the community.<br /><br />For developers interested to create their own strategies, please see [Developers: Strategies](/developers/strategies).

<br />
