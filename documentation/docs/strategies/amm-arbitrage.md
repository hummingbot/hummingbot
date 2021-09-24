---
tags:
- arbitrage
---

# `amm_arb`

## 📁 [Strategy folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/strategy/amm_arb)

## 📝 Summary



## 🏦 Exchanges supported

[`amm` exchanges](/exchanges/#amm)
[`spot` exchanges](/exchanges/#spot)

## 👷 Maintainer

Open

## 🛠️ Strategy configs

[Config map](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/amm_arb/amm_arb_config_map.py)

| Parameter                    | Type        | Default     | Prompt New? | Prompt                                                 |
|------------------------------|-------------|-------------|-------------|--------------------------------------------------------|
| `connector_1` | string | | True | Enter your first spot connector (Exchange/AMM) |
| `market_1` | string | | True | Enter the token trading pair you would like to trade on [connector_1] |
| `connector_2` | string | | True | Enter your second spot connector (Exchange/AMM) |
| `market_2` | string | | True | Enter the token trading pair you would like to trade on [connector_2] |
| `order_amount` | decimal | | True | What is the amount of [base_asset] per order? |
| `min_profitability` | decimal | 1 | True | What is the minimum profitability for you to make a trade? |
| `market_1_slippage_buffer` | decimal | 0.05 | True | How much buffer do you want to add to the price to account for slippage for orders on the first market |
| `market_2_slippage_buffer` | decimal | 0 | True | How much buffer do you want to add to the price to account for slippage for orders on the second market |
| `concurrent_orders_submission` | bool | False | True | Do you want to submit both arb orders concurrently (Yes/No) ? If No, the bot will wait for first connector order filled before submitting the other order |
| `use_oracle_conversion_rate` | bool | | True | Do you want to use rate oracle on unmatched trading pairs? (Yes/No) |
| `secondary_to_primary_quote_conversion_rate` | decimal | 1 | False | Enter conversion rate for secondary quote asset value to primary quote asset value |

## 📓 Description
