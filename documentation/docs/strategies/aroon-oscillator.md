---
hide:
- toc
tags:
- 👨‍👩‍👧‍👦 community contribution
- market making
- ⛏️ liquidity mining strategy
---

# `aroon_oscillator`

## 📁 [Strategy folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/strategy/aroon_oscillator)

## 📝 Summary

This strategy is a modified version of the Pure Market Making strategy that uses the [Aroon technical indicator](https://www.investopedia.com/terms/a/aroon.asp#:~:text=The%20Aroon%20indicator%20is%20a,lows%20over%20a%20time%20period) to adjust order spreads based on the uptrend or downtrend signified by the indicator.

This strategy was the winning submission in the Hummingbot track of the [Open DeFi hackathon](https://hummingbot.io/blog/2021-05-opendefi-hackathon-hummingbot-bounty-winner).

## 🏦 Exchanges supported

[`spot` exchanges](/exchanges/#spot)

## 👷 Maintenance

* Release added: [0.45.0](/release-notes/0.45.0/) by [squarelover](https://github.com/squarelover)
* Maintainer: Open

## 🛠️ Strategy configs

[Config map](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/aroon_oscillator/aroon_oscillator_config_map.py)

| Parameter                        | Type        | Default     | Prompt New? | Prompt                                                 |
|----------------------------------|-------------|-------------|-------------|--------------------------------------------------------|
| `exchange`                       | string      |             | True        | Enter your maker spot connector                        |
| `market`                         | string      |             | True        | Enter the token trading pair you would like to trade on [exchange] |
| `minimum_spread`                 | decimal     |             | True        | What is the closest to the mid price should the bot automatically create orders for? |
| `maximum_spread`                 | decimal     |             | True        | What is the farthest away from the mid price do you want the bot automatically create orders for? |
| `period_length`                  | int         | 25          | True        | How many time periods will be used to calculate the Aroon Oscillator? This indicator typically uses a timeframe of 25 periods however the timeframe is subjective. Use more periods to get fewer waves and smoother trend indicator. Use fewer periods to generate more waves and quicker turnarounds in the trend indicator. |
| `period_duration`                | int         | 60          | True        | How long in seconds are the Periods in the Aroon Oscillator? |
| `minimum_periods`                | int         | 1           | True        | How long in seconds are the Periods in the Aroon Oscillator? |
| `aroon_osc_strength_factor`      | decimal     | 0.5         | True        | How strong will the Aroon Osc value affect the spread adjustement? A strong trend indicator (when Aroon Osc is close to -100 or 100) will increase the trend side spread, and decrease the opposite side spread. Values below 1 will decrease its affect, increasing trade likelihood, but decrease risk. |
| `order_refresh_time`             | float       |             | True        | How often do you want to cancel and replace bids and asks (in seconds)? |
| `order_amount`                   | decimal     |             | True        | What is the amount of [base_asset] per order? |
| `max_order_age`                  | float       | 1800        | False       | How often do you want to cancel and replace bids and asks with the same price (in seconds)? |
| `order_refresh_tolerance_pct`    | decimal     | 0           | False       | Enter the percent change in price needed to refresh orders at each cycle |
| `cancel_order_spread_threshold`  | decimal     | 0           | False       | Enter the percent change in price needed to refresh orders at each cycle |
| `price_ceiling`                  | decimal     | -1          | False       | Enter the price point above which only sell orders will be placed |
| `price_floor`                    | decimal     | -1          | False       | Enter the price below which only buy orders will be placed |
| `order_levels`                   | int         | 1           | False       | How many orders do you want to place on both sides? |
| `order_level_amount`             | decimal     | 0           | False       | How much do you want to increase or decrease the order size for each additional order? |
| `order_level_spread`             | decimal     | 0           | False       | Enter the price increments (as percentage) for subsequent orders? |
| `inventory_skew_enabled`         | bool        | False       | False       | Would you like to enable inventory skew? |
| `inventory_target_base_pct`      | decimal     | 50          | False       | What is your target base asset percentage? |
| `inventory_range_multiplier`     | decimal     | 50          | False       | What is your tolerable range of inventory around the target, expressed in multiples of your total order size? |
| `inventory_price`                | decimal     | 1           | False       | What is the price of your base inventory? |
| `filled_order_delay`             | decimal     | 60          | False       | How long do you want to wait before placing the next order if your order gets filled (in seconds)? |
| `hanging_orders_enabled`         | bool        | False       | False       | Do you want to enable hanging orders? |
| `hanging_orders_cancel_pct`      | decimal     | 10          | False       | At what spread percentage (from mid price) will hanging orders be canceled?|
| `order_optimization_enabled`     | bool        | False       | False       | Do you want to enable best bid ask jumping? |
| `ask_order_optimization_depth`   | decimal     | 0           | False       | How deep do you want to go into the order book for calculating the top ask, ignoring dust orders on the top (expressed in base asset amount)?|
| `bid_order_optimization_depth`   | decimal     | 0           | False       | How deep do you want to go into the order book for calculating the top bid, ignoring dust orders on the top (expressed in base asset amount)?|
| `add_transaction_costs`          | bool        | False       | False       | Do you want to add transaction costs automatically to order prices? |
| `price_type`                     | decimal     | 1           | False       | Which price type to use (mid_price/last_price/last_own_trade_price/best_bid/best_ask/inventory_cost) |
| `take_if_crossed`                | bool        | False       | False       | Do you want to take the best order if orders cross the orderbook? |
| `order_override`                 | bool        | None        | False       |  |

## 📓 Description

[Trading logic](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/aroon_oscillator/aroon_oscillator.pyx)

!!! note "Approximation only"
    The description below is a general approximation of this strategy. Please inspect the strategy code in **Trading Logic** above to understand exactly how it works.

*By [squarelover](https://github.com/squarelover) - see original [pull request](https://github.com/CoinAlpha/hummingbot/pull/3430)*

One of the major downsides to many of the Market-Making strategies in Hummingbot is that they don't understand trends. In my experience, I've often had my bots trade on the wrong side of a trend. This is what it frequently looks like: 
![Bad Bad Bot, No Good!](https://www.dropbox.com/temp_thumb_from_token/s/2q3j6mnnqup0bl4?preserve_transparency=False&size=1200x1200&size_mode=4)
_Bad Bad Bot, No Good!_ ⬆️

My strategy attempts to take a well-known set of Market Indicators called Aroon Indicators. These indicators collect trade prices over a configurable set of periods of a given duration. The indicators represent how recent the highest highs and the lowest lows are. And the Oscillator indicator can strongly suggest a market trend. I've tried to distill what the indicators signify and use them to adjust spreads so traders are positioned at the hopefully the best point to execute at profitable positions. In other words, it tries to be better at buying low and selling high.

Here's a screenshot of the status screen:
![Aroon Indicators](https://www.dropbox.com/temp_thumb_from_token/s/2vjh58hkbscrvh6?preserve_transparency=False&size=1200x1200&size_mode=4)

You can learn more about Aroon Indicators, here:
https://www.investopedia.com/terms/a/aroon.asp

AroonOscillatorStrategy is a market-making strategy that uses Aroon Indicators to detect trends.
A user will set up the number of periods in the Indicator and how long each period is in seconds.
The user also sets a minimum and maximum spread that they desire. Then the indicator will use the
collected period data to automatically adjust the spreads to try and position orders at the best
spot for profitable trades.

Traditionally the number of periods is 25, but any amount can be used. Lower numbers will produce
more oscillations, which in turn will adjust the spreads more drastically. Higher numbers will produce
less oscillations, this will adjust the spreads more smoothly.

The time duration of the period can be chosen to best suit your trade strategy. For example if you use
5 minute candles when analysing market data, set the duration to 300 seconds.

`minimum_periods` can be set to have the indicator engage adjusting the spreads before the Indicator
periods fill up. Set this to -1 to have only adjust spreads when the indicator is full.

The strategy will adjust the `bid_spread` closer to `minimum_spread` the closer Aroon Down indicator gets to 100. It will adjust the `ask_spread` closer to the `minimum_spread` the closer Aroon Up gets to 100. 

The spread is further adjusted by the Aroon Oscillator indicator. If the indicator strongly
suggests a trend, it will push the spread out further from `minimum_spread` in order to wait for a more optimal
point to trade. The effect of the oscillator indicator can be adjusted by the `aroon_osc_strength_factor` parameter
a setting lower than 1.0 will decrease its effect on the spread during a strong trend.

The rest of the strategy is pretty much copied from PureMarketMakingStrategy. A few options have been removed
such as the pricing delegates. There are more features that could possibly be removed since they don't work
well with the Indicator.