---
tags:
- market making
- ⛏️ liquidity mining strategy
---

# `avellaneda_market_making`

## 📁 [Strategy folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/strategy/avellaneda_market_making)

## 📝 Summary

This strategy implements a market making strategy described in the classic paper [High-frequency Trading in a Limit Order Book](https://people.orie.cornell.edu/sfs33/LimitOrderBook.pdf) written by Marco Avellaneda and Sasha Stoikov. It allows users to directly adjust the `gamma` parameter described in the paper. It also features an order book liquidity estimator calculating the `alpha` and `kappa` parameters automatically. Additionally, the strategy implements the order size adjustment algorithm and its `eta` parameter as described in [Optimal High-Frequency Market Making](http://stanford.edu/class/msande448/2018/Final/Reports/gr5.pdf). The strategy is implemented to be used either in fixed timeframes or to be ran indefinitely.

## 🏦 Exchanges supported

[`spot` exchanges](/exchanges/#spot)

## 👷 Maintenance

* Release added: [0.38.0](/release-notes/0.38.0/) by CoinAlpha
* Maintainer: CoinAlpha

## 🛠️ Strategy configs

[Config map](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/avellaneda_market_making/avellaneda_market_making_config_map.py)


| Parameter                    | Type        | Default     | Prompt New? | Prompt                                                 |
|------------------------------|-------------|-------------|-------------|--------------------------------------------------------|
| `exchange`                   | string      |             | True        | Enter your maker spot connector |
| `market`                     | string      |             | True        | Enter the token trading pair you would like to trade on `exchange`|
| `execution_timeframe`        | string      |             | True        | Choose execution timeframe ( `infinite` / `from_date_to_date` / `daily_between_times` ) | 
| `start_time`                 | string      |             | Conditional | Please enter the start date and time (YYYY-MM-DD HH:MM:SS) OR Please enter the start time (HH:MM:SS) |
| `end_time`                   | string      |             | Conditional | Please enter the end date and time (YYYY-MM-DD HH:MM:SS) OR Please enter the end time (HH:MM:SS) |
| `order_amount`               | decimal     |             | True        | What is the amount of `base_asset` per order?|
| `order_optimization_enabled` | bool        |  True       | False       | Do you want to enable best bid ask jumping? |
| `risk_factor`                | decimal     |  Computed   | False       | Enter risk factor (𝛾) |
| `order_amount_shape_factor`  | decimal     |  Computed   | False       | Enter order amount shape factor (η) |
| `min_spread`                 |             |  0          | True        | Enter minimum spread limit (as % of mid price) |
| `order_refresh_time`         | decimal     |             | True        | How often do you want to cancel and replace bids and asks (in seconds)? |
| `max_order_age`              | decimal     |  1800       | False       | How long do you want to cancel and replace bids and asks with the same price (in seconds)? |
| `order_refresh_tolerance_pct`| decimal     |  0          | False       | Enter the percent change in price needed to refresh orders at each cycle |
| `filled_order_delay`         | decimal     |  60         | False       | How long do you want to wait before placing the next order if your order gets filled (in seconds)? |
| `inventory_target_base_pct`  | decimal     |  50         | True        | What is the inventory target for the base asset? |
| `add_transaction_costs`      | decimal     |  False      | False       | Do you want to add transaction costs automatically to order prices? (Yes/No) |
| `volatility_buffer_size`     | decimal     |  200        | False       | Enter amount of ticks that will be stored to calculate volatility |
| `trading_intensity_buffer_size` | decimal     |  200        | False       | Enter amount of ticks that will be stored to estimate order book liquidity? |
| `order_levels`               | int         |  1          | False       | How many orders do you want to place on both sides? |
| `level_distances`            | decimal     |  0          | False       | How far apart in % of optimal spread should orders on one side be? |
| `order_override`             | json        |             | False       |  |
| `hanging_orders_enabled`     | bool        |  False      | False       | Do you want to enable hanging orders? (Yes/No) |
| `hanging_orders_cancel_pct`  | decimal     |  10         | False       | At what spread percentage (from mid price) will hanging orders be canceled? |
| `should_wait_order_cancel_confirmation` |  bool |  True       | False       | Should the strategy wait to receive a confirmation for orders cancellation before creating a new set of orders? (Not waiting requires enough available balance) (Yes/No) |

## 📓 Description

[Trading logic](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/avellaneda_market_making/avellaneda_market_making.pyx)

!!! note "Approximation only"
    The description below is a general approximation of this strategy. Please inspect the strategy code in **Trading Logic** above to understand exactly how it works.

### Architecture

The strategy continuously calculates optimal positioning of a market maker's buy and sell limit orders within an order book, taking into account the current order book liquidity, the asset volatility, the desired portfolio allocation and the trading session timeframe. Orders are being placed symmetrically around a so called reserved price, which may or may not be identical to the mid price. 

The farther the current portfolio is from the desired asset allocation (as defined by the `inventory_target_base_pct` parameter), the farther away is the reserved price from the mid price, skewing probabilites of either buy or sell orders being filled. If the strategy needs an asset to be sold, sell orders will be placed closer to the mid price than buy orders, and vice versa. 

Limit prices of orders are also a function of order book liquidity and asset volatility. The strategy generally tries to place orders as close to the mid price as possible, without them being filled. The less liquid an order book is, the farther away the orders will be placed. Also the more volatile an asset is, the farther away the orders will be placed. 

If the strategy is running in a finite timeframe, the closer it is to the end of the trading session, the closer the reserved price will be to the mid price, once the portfolio is in a desired state.

The `risk_factor` or `gamma` also influence calculation of the reserved price and order placement. Generally the higher the value, the more aggressive the strategy will be, and the farther away from the mid price the reserved price will be. It's a unit-less parameter, that can be set to any non-zero value as necessary. Generally it should be higher for assets with lower prices, and lower for assets with higher prices. 

Given the right market conditions and the right `risk_factor`, it's possible that the optimal spread will be wider than the absolute price of the asset, or that the reserved price will by far away from the mid price, in both cases resulting in the optimal bid price to be lower than or equal to 0. In that case neiher buy or sell will be placed. To prevent this from happening, users should set the `risk_factor` to a lower value.

If users choose to set the `eta` parameter, order sizes will be adjusted to further optimize the strategy behavior in regards to the current and desired portfolio allocation.

Users have an option to layer orders on both sides. If more than 1 `order_levels` are chosen, multiple buy and sell limit orders will be created on both sides, with predefined price distances from each other, with the levels closest to the reserved price being set to the optimal bid and ask prices. This price distance between levels is defined as a percentage of the optimal spread calculated by the strategy. The percentage is given as the `level_distances` parameter. Given that optimal spreads tend to be tight, the `level_distances` values should be in general in tens or hundreds of percents.



![Figure 1: Strategy flow chart](/assets/img/avellaneda.svg)


### Timeframes

The original Avellaneda-Stoikov strategy was designed to be employed for market making on stock markets, which have defined trading hours. Its timeframe was therefore finite. For crypto markets there are no trading hours, crypto markets trade 24/7. The strategy should therefore be designed to run indefinitely. However in some cases users may want to run the strategy only between specific dates or only bewteen specific times of a day. For this the strategy offers 3 different modes: `infinite`, `from_date_to_date` and `daily_between_times`. 

For the `infinite` timeframe the equations used to calculate the reserved price and the optimal spread are slightly different, because the strategy doesn't have to take into account the time left until the end of a trading session. 

Both the `start_time` and the `end_time` parameters are defined to be in the local time of the computer on which the client is running. For the `infinite` timeframe these two parameters have no effect.


### Asset Characteristics Estimation

The strategy calculates the reserved price and the optimal spread based on measurements of the current asset volatility and the order book liquidity. The asset volatility estimator is implemented as the `instant_volatility` indicator, the order book liquidity estimator is implemented as the `trading_intensity` indicator. 

Before any estimates can be given, both estimators need to have their buffers filled. By default the lengths of these buffers are set to be 200 ticks. In case of the `trading_intensity` estimator only order book snapshots different from preceding snapshots count as valid ticks. Therefore the strategy may take longer than 200 seconds (in case of the default length of the buffer) to start placing orders.

The `trading_intensity` estimator is designed to be consistent with ideas outlined in the Avellaneda-Stoikov paper. The `instant_volatility` estimator defines volatility as a deviation of prices from one tick to another in regards to a zero-change price action.


### Minimum Spread

The `minimum_spread` parameter is optional, it has no effect on the calculated reserved price and the optimal spread. It serves as a hard limit below which orders won't be placed, if users  choose to ensure that buy and sell orders won't be placed too close to each other, which may be detrimental to the market maker's earned fees. The minimum spread is given by the `minimum_spread` parameter as a percentage of the mid price. By default its value is 0, therefore the strategy places orders at optimal bid and ask prices.


