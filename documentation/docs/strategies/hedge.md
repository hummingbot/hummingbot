---
hide:
- toc
tags:
- 👨‍👩‍👧‍👦 community contribution
- utility strategy
---

# `hedge`

## 📁 [Strategy folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/strategy/hedge)

## 📝 Summary

This strategy allows you to hedge a market making strategy by automatically opening short positions on [`dydx_perpetual`](/exchanges/dydx-perpetual) or another `perp` exchange. Configs like `hedge_ratio` allow you to customize how much to hedge. Users are expected to run this strategy alongside another market making strategy.

This strategy was the winning submission in the [dYdX hackathon](https://hummingbot.io/blog/dYdX-Bounty-Winner-Announcement). 

## 🏦 Exchanges supported

[`perp` exchanges](/exchanges/#perp)

## 👷 Maintenance

* Release added: [0.45.0](/release-notes/0.45.0/) by [leastchaos](https://github.com/leastchaos)
* Maintainer: Open

## 🛠️ Strategy configs

[Config map](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/hedge/hedge_config_map.py)

| Parameter                        | Type        | Default     | Prompt New? | Prompt                                                 |
|----------------------------------|-------------|-------------|-------------|--------------------------------------------------------|
| `maker_exchange`                 | string      |             | True        | Enter the spot connector to use for target market      |
| `maker_assets`                   | string      |             | True        | Enter a list of assets to hedge on taker market(comma separated, e.g. LTC,ETH) |
| `taker_exchange`                 | string      |             | True        | Enter the derivative connector to use for taker market |
| `taker_markets`                  | string      |             | True        | Enter a list of markets to execute on taker market for each asset(comma separated, e.g. LTC-USDT,ETH-USDT) |
| `hedge_interval`                 | decimal     | 10          | True        | how often do you want to check the hedge |
| `hedge_ratio`                    | decimal     | 1           | True        | Enter ratio of base asset to hedge, e.g 0.5 -> 0.5 BTC will be short for every 1 BTC bought on maker market |
| `leverage`                       | decimal     | 10          | True        | How much leverage do you want to use? |
| `max_order_age`                  | float       | 100         | True        | Max Order Age in seconds? |
| `slippage`                       | decimal     | 0.01        | True        | Enter max slippage in decimal, e.g 0.1 -> 10% |
| `minimum_trade`                  | decimal     | 10          | True        | Enter minimum trade size in hedge asset |

## 📓 Description

[Trading logic](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/hedge/hedge.pyx)

!!! note "Approximation only"
    The description below is a general approximation of this strategy. Please inspect the strategy code in **Trading Logic** above to understand exactly how it works.

*By [leastchaos](https://github.com/leastchaos) - see original [pull request](https://github.com/CoinAlpha/hummingbot/pull/4121)*

**Summary**

This strategy looks at the balance of the position on the spot(maker) exchange, and hedges it on the perpetual(taker) exchange.

**Code Logic:**

On every hedge_interval seconds,
1. Look at balance of the for each asset defined under maker_asset on the maker markets
2. Compares the balance of each asset on the maker markets with the positions on the taker markets
3. If there is a difference more than the minimum trade, execute an order to balance the trade back to the target net position based on hedge ratio and maker asset balance.
E.g if maker markets has 1BTC and taker market is -0.2 BTC (short position), if hedge ratio is defined as 0.5.
The target net position will be 0.5 * 1BTC (from maker market) =0.5BTC.
it will then execute a sell order of (0.5BTC-0.2BTC) = 0.3BTC on the taker market so that the net position of both market is 0.5BTC.

**Strategy Configuration:**

- maker_exchange: Define the spot market
- maker_asset: Define the list of markets to monitor on the maker exchange e.g LTC,BTC,ETH
- taker_exchange: Define the perpetual market to hedge the spot market.
- taker_markets: Define the list of markets to hedge on for each asset
- e.g LTC-USD,BTC-USD,ETH-USD means LTC (from maker_asset first element) will be hedged on  LTC-USD (taker_market first element) and so on, BTC -> BTC-USD, ETH->ETH-USD
- hedge_interval: set time interval for each loop in seconds. (Can be <1 to get a faster hedge but you may encounter issue such as rate limit. use at your own risk)
- hedge_ratio: set ratio of assets to be hedged on taker exchange. e.g 1 -> 100% of balance will be hedged. 0.5 -> 50% of balance will be hedged , 2-> 200% of balance will be hedged.
- leverage: set the leverage to be used at the taker exchange
- max_order_age: maximum time in seconds for limit order of hedge to be active before retry
- slippage: set the initial buy/sell price. For buys, the buy price will be placed at min ask on taker market * (1+slippage), for sells, the sell order price will be placed at max bid on taker market* (1-slippage)
- minimum_trade: set the minimum difference required between taker and maker balance in order to submit an order for hedging. This need to higher than or equal to the minimum trade size of the taker exchange

**Sample Use Case Examples**

- Can also use with humming bot standard strategy and personal custom strategy or trading bot other than hummingbot to trade on spot exchange and define hedge ratio to hedge a percentage of trade or even opposite trade made on spot exchange on the perpetual exchange

**Notes from CoinAlpha QA**

- `perp` exchanges: tested on `dydx_perpetual` and `binance_perpetual`
- `spot` exchange: tested on `ascend_ex` and `binance`
- On `dydx_perpetual`, `hedge_interval` <1 may cause issue such as unexpected clock tick error and rate limit
- On `binance_perpetual`, `hedge_interval` has been tested to work with 0.01s