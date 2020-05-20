# Strategies

The current release of Hummingbot comes with 3 strategies:

## [Pure Market Making](./pure-market-making)

Post buy and sell offers for an instrument on a single exchange, automatically adjust prices while actively managing inventory.

For experienced users of this strategy, see [Advanced Market Making](./advanced-mm) for how to use more sophisticated features of this strategy.

## [Cross Exchange Market Making](/strategies/cross-exchange-market-making)

Also referred to as *liquidity mirroring* or *exchange remarketing*.  In this strategy, Hummingbot makes markets (creates buy and sell orders) on smaller or less liquid exchanges and does the opposite, back-to-back transaction for any filled trades on a more liquid exchange.

## [Arbitrage](./arbitrage)

Aims to capture price differentials between two different exchanges (buy low on one, sell high on the other).

The [Hummingbot whitepaper](https://www.hummingbot.io/hummingbot.pdf) provides more details about these strategies, as well as additional ones that we are working on for future versions of Hummingbot.

## For Developers

These strategies are meant to be basic templates. We encourage users to extend these templates for their own purposes, and if they so desire, share them with the community.

For developers interested to create their own strategies, please see [Strategies](/developers/strategies) in the Developer Manual.