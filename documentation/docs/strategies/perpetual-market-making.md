---
tags:
- market making
- perp strategy
---

# `perpetual_market_making`

## 📁 [Strategy folder](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/perpetual_market_making)

## 📝 Summary

This strategy allows Hummingbot users to run a market making strategy on a single trading pair on a perpetuals swap (`perp`) order book exchange.

Similar to the `pure_market_making_strategy`, the `perpetual_market_making` strategy keeps placing limit buy and sell orders on the order book and waits for other participants (takers) to fill its orders. But unlike market making on spot markets, where assets are being exchanged, market making on perpetual markets creates and closes positions. Since outstanding perpetual swap positions are created after fills, the strategy has a number of parameters to determine when positions are closed to take profits and prevent losses.

## 🏦 Exchanges supported

[`perp` exchanges](/exchanges/#perp)

## 👷 Maintenance

* Release added: [0.36.0](/release-notes/0.36.0/) by CoinAlpha
* Maintainer: CoinAlpha

## 🛠️ Strategy configs

[Config map](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/perpetual_market_making/perpetual_market_making_config_map.py)

| Parameter                    | Type        | Default     | Prompt New? | Prompt                                                 |
|------------------------------|-------------|-------------|-------------|--------------------------------------------------------|
| `derivative`                 | string      |             | True        | Enter your maker derivative connector |
| `market`                     | string      |             | True        | Enter the trading pair you would like to provide liquidity on [exchange] |
| `leverage`                   | int         |             | True        | How much leverage do you want to use? |
| `position_mode`              | string      | One-way     | True        | Which position mode do you want to use? (One-way/Hedge) |
| `bid_spread`                 | decimal     |             | True        | How far away from the mid price do you want to place the first bid order? |
| `ask_spread`                 | decimal     |             | True        | How far away from the mid price do you want to place the first ask order? |
| `minimum_spread`             | decimal     | -100        | False       | At what minimum spread should the bot automatically cancel orders? |
| `order_refresh_time`         | float       |             | True        | How often do you want to cancel and replace bids and asks (in seconds)? |
| `order_refresh_tolerance_pct`| decimal     | 0           | False       | Enter the percent change in price needed to refresh orders at each cycle |
| `order_amount`               | decimal     |             | True        | What is the amount of [base_asset] per order? |
| `long_profit_taking_spread`  | decimal     | 0           | True        | At what spread from the entry price do you want to place a short order to reduce position? |
| `short_profit_taking_spread` | string      | 0           | True        | At what spread from the position entry price do you want to place a long order to reduce position? |
| `stop_loss_spread`           | string      | 0           | True        | At what spread from position entry price do you want to place stop_loss order? |
| `time_between_stop_loss_orders` | decimal    | 60        | True        | How much time should pass before refreshing a stop loss order that has not been executed? (in seconds) |
| `stop_loss_slippage_buffer`  | decimal     | 0.5         | True        | How much buffer should be added in stop loss orders' price to account for slippage (Enter 1 for 1%)? |
| `price_ceiling`              | decimal     | -1          | False       | Enter the price point above which only sell orders will be placed |
| `price_floor`                | decimal     | -1          | False       | Enter the price below which only buy orders will be placed |
| `order_levels`               | int         | 1           | False       | How many orders do you want to place on both sides? |
| `order_level_amount`         | decimal     | 0           | False       | How much do you want to increase or decrease the order size for each additional order? (decrease < 0 > increase) |
| `order_level_spread`         | decimal     | 1           | False       | Enter the price increments (as percentage) for subsequent orders? (Enter 1 to indicate 1%) |
| `filled_order_delay`         | float       | 60          | False       | How long do you want to wait before placing the next order if your order gets filled (in seconds)? |
| `order_optimization_enabled` | bool        | False       | False       | Do you want to enable best bid ask jumping? (Yes/No) |
| `ask_order_optimization_depth` | decimal   | 0           | False       | How deep do you want to go into the order book for calculating the top ask, ignoring dust orders on the top (expressed in base asset amount)? |
| `bid_order_optimization_depth` | decimal   | 0           | False       | How deep do you want to go into the order book for calculating the top bid, ignoring dust orders on the top (expressed in base asset amount)? |
| `price_source`               | string      | current_market | False    | Which price source to use? (current_market/external_market/custom_api) |
| `price_type`                 | string      | mid_price   | False       | Which price type to use? (mid_price/last_price/last_own_trade_price/best_bid/best_ask) |
| `price_source_derivative`    | string      |             | False       | Enter external price source connector name or derivative name |
| `price_source_market`        | string      |             | False       | Enter the token trading pair on [external_market] |
| `price_source_custom_api`    | string      |             | False       | Enter pricing API URL |
| `custom_api_update_interval` | float       | 5           | False       | Enter custom API update interval in second (default: 5.0, min: 0.5) |
| `order_override`             | json        |             | False       | |

## 📓 Description

[Trading logic](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/perpetual_market_making/perpetual_market_making.pyx)

!!! note "Approximation only"
    The description below is a general approximation of this strategy. Please inspect the strategy code in **Trading Logic** above to understand exactly how it works.

### Architecture

The `perpetual_market_making` strategy works in a similar fashion as the `pure_market_making_strategy`, except adapted to trading perpetual swaps. Trading perpetual swaps creates positions, and doesn't just exchage assets like trading on spot markets.

On every tick the strategy creates new opening orders and existing orders are being cancelled. If an outstanding order is filled, the strategy then has to manage the position. 

![Figure 1: General strategy flow chart](/assets/img/perp_mm-flowchart-1.svg)

### Order Placement

The strategy places long and short orders to open perpetual swap positions at predefined distances from a mid price. These distances are given by the parameters `bid_spread` and `ask_spread`. 

On every tick, outstanding open orders are being evaluated. If they're too far from the proposal orders, as defined by the `order_refresh_tolerance_pct` parameter, they will be cancelled and replaced by new orders.
If an active order finds itself below a `min_spread` threshold from the mid price, it will also be cancelled.

It's also possible to place multiple orders on each side in price layers as defined by the parameters `order_levels`, `order_level_amount` and `order_level_spread`. The closest to the mid price will be always orders at distances `bid_spread` and `ask_spread`.

The strategy can be restricted to trade only within a specific price band, defined by the `price_ceiling` and `price_floor` parameters. If the mid price is outside of this interval, no orders will be created, only cancelled.

![Figure 2: Order creation and adjustment flow chart](/assets/img/perp_mm-flowchart-2.svg)

### Position Management

New opening orders are not being placed if one or more of existing opening orders were filled and the strategy holds a position. In that case, the position(s) is being evaluated on every tick whether to close it or not, and whether to either take a profit or a loss. These decisions are controlled by parameters `long_profit_taking_spread`, `short_profit_taking_spread` and `stop_loss_spread`.

![Figure 3: Position management flow chart](/assets/img/perp_mm-flowchart-3.svg)




