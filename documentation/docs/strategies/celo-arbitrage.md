---
tags:
- arbitrage
- dex strategy
- celo
---

# `celo_arb`


## 📁 [Strategy folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/strategy/celo_arb)

## 📝 Summary

This strategy is a predecessor to the `amm_arb` strategy built specifically to help [Celo Protocol](https://celo.org/) maintain price stability for its stablecoin pairs. Like `amm_arb`, this strategy monitors prices between AMM-based exchanges on the Celo blockchain versus another trading pair on another `spot` or `amm` exchange in order to identify arbitrage opportunities. 

It executes offsetting buy and sell orders in both markets in order to capture arbitrage opportunities with profitability higher than `min_profitability`, net of transaction costs, which include both blockchain transaction fees (gas) and exchange fees.

!!! note
    Currently, this strategy requires users to install the `celo-cli` tool alongside Hummingbot. In the future, CoinAlpha plans to add a Celo connector to [Gateway](/protocols/gateway) so that the generic `amm_arb` strategy works with Celo.

## 🏦 Exchanges supported

* [Celo protocol](/protocols/celo)
* [`spot` exchanges](/exchanges/#spot)

## 👷 Maintenance

* Release added: [0.28.0](/release-notes/0.28.0/) by CoinAlpha
* Maintainer: CoinAlpha

## 🛠️ Strategy configs

[Config map](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/celo_arb/celo_arb_config_map.py)

| Parameter                    | Type        | Default     | Prompt New? | Prompt                                                 |
|------------------------------|-------------|-------------|-------------|--------------------------------------------------------|
| `secondary_exchange` | string | | True | Enter your secondary spot connector |
| `secondary_market` | string | | True | Enter the token trading pair you would like to trade on [secondary_exchange] |
| `order_amount` | decimal | | True | What is the amount of [base_asset] per order? |
| `min_profitability` | decimal | 0.3 | True | What is the minimum profitability for you to make a trade? |
| `celo_slippage_buffer` | decimal | 0.01 | True | How much buffer do you want to add to the Celo price to account for slippage? |

## 📓 Description

[Trading logic](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/celo_arb/celo_arb.pyx)
