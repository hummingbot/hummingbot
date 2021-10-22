A Hummingbot strategy is a continual process that monitors trading pairs on one or more exchanges in order to make trading decisions. Strategies separate **trading logic**, open source code that defines how the strategy behaves, versus **parameters**, user-defined variables like spread and order amount that control how the strategy is deployed against live market conditions. Strategy parameters are stored in a local **config file** that is not exposed externally.

Strategies utilize the standardized trading interfaces exposed by exchange and protocol connectors, enabling developers to write code that can be used across many exchanges. Each Hummingbot strategy is a sub-folder in the [`/hummingbot/strategy`](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/strategy) folder.

## Strategy types

Hummingbot offers the following automated trading strategies, each with its own set of configurable parameters.

* **Market making**: strategies that provide liquidity to a market
* **Arbitrage**: strategies that exploit differences between markets
* **Utility**: other strategies

## Maintainer

Strategy maintainers are responsible for responding to community feedback, fixing bugs, and actively improving the strategy over time.

As the creator of Hummingbot, CoinAlpha maintains for most strategies, particularly the market making strategies. As the number of strategies grows, however, CoinAlpha will enable other community members to contribute and maintain strategies.

## Customizing strategies

These strategies are meant to be basic templates. We encourage users to extend these templates for their own purposes, and if they so desire, share them with the community.

Developers may submit strategies for review. Please note the [Contribution Guidelines](/developers/contributions/). For developers interested to create or customize their own strategies, please see [Strategies](/developers/strategies) in the Developers section.

## List of strategies

### Market making

Market making strategies help you provide liquidity to an exchange while mitigating risk by dynamically repositioning and/or hedging your orders.

  | Name                                                          | Valid Exchanges     | Maintainer    | Description                                                                       |
|-----------------------------------------------------------------|---------------------|---------------|-----------------------------------------------------------------------------------|
| [`avellaneda_market_making`](./avellaneda-market-making)        | `spot`              | CoinAlpha     | Single-pair market making strategy based on the classic Avellaneda-Stoikov paper  |
| [`aroon_oscillator`](./aroon_oscillator)                        | `spot`              |               | Modified version of Pure Market Making that uses Aroon technical indicator (Open DeFi hackathon winner) |
| [`cross_exchange_market_making`](./cross-exchange-market-making)| `spot`              | CoinAlpha     | Provide liquidity while hedging filled orders on another exchange                |
| [`liquidity_mining`](./liquidity-mining)                        | `spot`              | CoinAlpha     | Provide liquidity on multiple pairs using a single base or quote token            |
| [`perpetual_market_making`](./perpetual-market-making)          | `perp`              | CoinAlpha     | Market-making strategy for perpetual swap markets                                 |
| [`pure_market_making`](./pure-market-making)                    | `spot`              | CoinAlpha      | Our original single-pair market making strategy                                  |
| [`uniswap_v3_lp`](./uniswap-v3-lp)                              | [`uniswap-v3`](/exchanges/uniswap-v3)| CoinAlpha | Manage liquidity positions on Uniswap-V3 style AMMs                  |

### Arbitrage

Arbitrage strategies help you monitor different markets for opportunities to realize an arbitrage profit and capture them when they arise.

| Name                                                            | Valid Exchanges     | Maintainer    | Description                                                                               |
|-----------------------------------------------------------------|---------------------|---------------|-------------------------------------------------------------------------------------------|
| [`amm_arb`](./amm-arbitrage)                                    | `spot`, `amm`       | CoinAlpha     | Exploits price differences between AMM and spot exchanges                                 |
| [`arbitrage`](./arbitrage)                                      | `spot`              |               | Exploits price differences between two different spot exchanges                           |
| [`celo-arb`](./celo-arbitrage)                                  | [`celo`](/protocols/celo)|          | Exploits price differences between Celo and other exchanges                               |
| [`spot_perpetual_arbitrage`](./spot-perpetual-arbitrage)        | `spot`, `perp`      | CoinAlpha     | Exploits price differences between spot and perpetual swap exchanges                      |

### Utility

| Name                                                            | Valid Exchanges     | Maintainer    | Description                                                                               |
|-----------------------------------------------------------------|---------------------|---------------|-------------------------------------------------------------------------------------------|
| [`hedge`](./hedge)                                              | `perp`              |               | Hedges spot exchange inventory risk using perpetual swaps (dYdX hackathon winner)         |
| [`twap`](./twap)                                                | `spot`              |               | Places a batch of limit orders over a period of time                                      |
| `vwap`                                                          | `spot`              |               | Places a batch of limit orders based on order book volume                                 |
