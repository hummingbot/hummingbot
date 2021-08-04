# Strategies

Hummingbot supports 11 different strategies:

## Market Making

Market making strategies help you provide liquidity to an exchange while mitigating risk by dynamically repositioning and/or hedging your orders.

### [Pure Market Making](./pure-market-making)

Post buy and sell offers for an instrument on a single exchange, automatically adjust prices while actively managing inventory.

### [Liquidity Mining](./liquidity-mining)

Liquidity mining allows users to run multiple market making bots on different pairs without the same base or quote are not available at the same time. Reduced the number of parameters needed and has dynamic spread adjustment on market volatility.

### [Avellaneda](./avellaneda-market-making)

Based on the seminal Avellaneda-Stoikov paper on market making, this strategy is a more advanced version of Pure Market Making.

### [Cross Exchange Market Making](./cross-exchange-market-making)

Also referred to as _liquidity mirroring_ or _exchange remarketing_. In this strategy, Hummingbot makes markets (creates buy and sell orders) on smaller or less liquid exchanges and does the opposite, back-to-back transaction for any filled trades on a more liquid exchange.

### [Perpetual Market Making](./perpetual-market-making)

Similar to pure market making but for exchanges that trade perpetual swaps.

### [Uniswap-v3-LP](./uniswap-v3-lp)

An experimental strategy that allows Uniswap-V3 liquidity providers to dynamically control placement and rebalancing of their positions.

## Arbitrage

Arbitrage strategies help you exploit price differences between exchanges.

### [Arbitrage](./arbitrage)

Aims to capture price differentials between two different exchanges (buy low on one, sell high on the other). The [Hummingbot whitepaper](https://www.hummingbot.io/hummingbot.pdf) provides more details about these strategies, as well as additional ones that we are working on for future versions of Hummingbot.

### [AMM Arbitrage](./amm-arbitrage)

AMM-arb lets you exploit the differences between AMMs like [Balancer](/protocol-connectors/balancer/) and order book exchanges like Binance. Extending the celo-arb strategy released a few months ago, amm-arb uses a new, simpler design that works with any AMM protocol, on both Ethereum and non-Ethereum chain. You can take a look on our supported [Protocol Connectors](/protocol-connectors/overview/) for this strategy

### [Celo Arbitrage](./celo-arb)

The celo-arb strategy is a special case of the normal arbitrage strategy that arbitrages between the automated market maker (AMM) exchange on the Celo blockchain and other markets supported by Hummingbot. This strategy allows users to earn arbitrage profits while contributing to the stability of the Celo cUSD price peg. For more information, please see this [blog post](https://hummingbot.io/blog/2020-06-celo-arbitrage/).

### [Spot Perpetual Arbitrage](./spot-perpetual-arbitrage)

The Spot Perpetual Arbitrage strategy lets you arbitrage between [Exchange connectors](/exchange-connectors/overview/) and derivatives connectors like [Binance Futures](/exchange-connectors/binance-futures/) and [Perpetual Finance](/protocol-connectors/perp-fi/). This strategy looks at the price on the spot connector and the price on the derivative connector. Then it calculates the spread between the two connectors.

## Misc

### [TWAP](./twap)

Place a batch of limit orders on an exchange over a period of time.

## For developers

These strategies are meant to be basic templates. We encourage users to extend these templates for their own purposes, and if they so desire, share them with the community.

For developers interested to create their own strategies, please see [Strategies](/developers/strategies) in the Developers section.