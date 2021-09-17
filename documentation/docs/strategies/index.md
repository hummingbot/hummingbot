A strategy is a continual process that monitor exchanges and make trading decisions. Each Hummingbot strategy is a sub-folder in the [`/hummingbot/strategy`](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/strategy) folder.

## Strategy types

Hummingbot offers the following automated trading strategies, each with its own set of configurable parameters.

* **Market making**: strategies that provide liquidity to a market
* **Arbitrage**: strategies that exploit differences between markets
* **Utility**: other strategies

!!! note "Core vs community maintenance"
    **Core** strategies are actively maintained and being improved by CoinAlpha or other core maintainers. **Community** strategies are not actively maintained, but we aim to fix bugs and address issues raised by the community.

### Market making

Market making strategies help you provide liquidity to an exchange while mitigating risk by dynamically repositioning and/or hedging your orders.

  | Name                                                          | Valid Exchanges     | Maintainer    | Description                                                                       |
|-----------------------------------------------------------------|---------------------|---------------|-----------------------------------------------------------------------------------|
| [`liquidity_mining`](./liquidity-mining)                        | `spot`              | CoinAlpha     | Provide liquidity on multiple pairs using a single base or quote token            |
| [`avellaneda_market_making`](./avellaneda-market-making)        | `spot`              | CoinAlpha     | Single-pair market making strategy based on the classic Avellaneda-Stoikov paper  |
| [`perpetual_market_making`](./perpetual-market-making)          | `perp`              | CoinAlpha     | Market-making strategy for perpetual swap markets                                 |
| [`uniswap_v3_lp`](./uniswap-v3-lp)                              | [`uniswap-v3`](/exchanges/uniswap-v3)| CoinAlpha | Manage liquidity positions on Uniswap-V3 style AMMs                 |
| [`pure_market_making`](./pure-market-making)                    | `spot`              | CoinAlpha      | Our original single-pair market making strategy                                   |
| [`cross_exchange_market_making`](./cross-exchange-market-making)| `spot`              | CoinAlpha      | Provide liquidity while hedging filled orders on another exchange                 |

### Arbitrage

Arbitrage strategies help you monitor different markets for opportunities to realize an arbitrage profit and capture them when they arise.

| Name                                                            | Valid Exchanges     | Maintainer    | Description                                                                               |
|-----------------------------------------------------------------|---------------------|---------------|-------------------------------------------------------------------------------------------|
| [`amm_arb`](./amm-arb)                                           | `spot`, `amm`       | CoinAlpha     | Exploits price differences between AMM and spot exchanges                                 |
| [`spot_perpetual_arbitrage`](./spot-perpetual-arbitrage)        | `spot`, `perp`      | CoinAlpha     | Exploits price differences between spot and perpetual swap exchanges                      |
| [`arbitrage`](./arbitrage)                                      | `spot`              | Community     | Exploits price differences between two different spot exchanges                           |
| [`celo-arb`](./celo-arb)                                        | [`celo`](/exchanges/celo)| Community | Exploits price differences between Celo and other exchanges                               |

### Utility

| Name                                                            | Valid Exchanges     | Maintainer    | Description                                                                               |
|-----------------------------------------------------------------|---------------------|---------------|-------------------------------------------------------------------------------------------|
| [`twap`](./twap)                                                | `spot`, `perp`      | Community     | Places a batch of limit orders over a period of time                                      |
| [`vwap`](./twap)                                                | `spot`, `perp`      | Community     | Places a batch of limit orders based on order book volume                                 |

## Customizing strategies

These strategies are meant to be basic templates. We encourage users to extend these templates for their own purposes, and if they so desire, share them with the community.

For developers interested to create or customize their own strategies, please see [Strategies](/developers/strategies) in the Developer Reference section.