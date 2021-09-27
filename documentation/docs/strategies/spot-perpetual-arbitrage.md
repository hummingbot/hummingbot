---
tags:
- arbitrage
- perp strategy
---

# `spot_perpetual_arbitrage`

## 📁 [Strategy folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/strategy/spot_perpetual_arbitrage)

## 📝 Summary

This strategy looks at the price on the spot connector and the price on the derivative connector. Then it calculates the spread between the two connectors. The key features for this strategy are `min_divergence` and `min_convergence`.

When the spread between spot and derivative markets reaches a value above `min_divergence`, the first part of the operation will be executed, creating a buy/sell order on the spot connector, while opening an opposing long/short position on the derivative connector.

With the position open, the bot will scan the prices on both connectors, and once the price spread between them reaches a value below `min_convergence`, the bot will close both positions.

## 🏦 Exchanges supported

[`spot` exchanges](/exchanges/#spot)
[`perp` exchanges](/exchanges/#perp)

## 👷 Maintainer

Open

## 🛠️ Strategy configs

[Config map](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/strategy/spot_perpetual_arbitrage/spot_perpetual_arbitrage_config_map.py)

| Parameter                    | Type        | Default     | Prompt New? | Prompt                                                 |
|------------------------------|-------------|-------------|-------------|--------------------------------------------------------|
| `spot_connector` | string | | True | Enter a spot connector (Exchange/AMM) |
| `spot_market` | string | | True | Enter the token trading pair you would like to trade on [spot_connector] |
| `derivative_connector` | string | | True | Enter a derivative name (Exchange/AMM) |
| `derivative_market` | string | | True | Enter the token trading pair you would like to trade on [derivative_connector] |
| `order_amount` | decimal | | True | What is the amount of [base_asset] per order? |
| `derivative_leverage` | int | 1 | True | How much leverage would you like to use on the derivative exchange? |
| `min_divergence` | decimal | 1 | True | What is the minimum spread between the spot and derivative market price before starting an arbitrage? |
| `min_convergence` | decimal | 0.1 | True | What is the minimum spread between the spot and derivative market price before closing an existing arbitrage? |
| `maximize_funding_rate` | bool | False | True | Would you like to take advantage of the funding rate on the derivative exchange, even if min convergence is reached during funding time? |
| `spot_market_slippage_buffer` | decimal | 0.05 | True | How much buffer do you want to add to the price to account for slippage for orders on the spot market |
| `derivative_market_slippage_buffer` | decimal | 0.05 | True | How much buffer do you want to add to the price to account for slippage for orders on the derivative market |
| `next_arbitrage_cycle_delay` | float | 120 | False | How long do you want the strategy to wait to cool off from an arbitrage cycle (in seconds) |

## 📓 Description
