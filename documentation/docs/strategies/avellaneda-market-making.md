---
tags:
- market making
- ⛏️ liquidity mining strategy
---

# `avellaneda_market_making`

## 📁 [Strategy folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/strategy/avellaneda_market_making)

## 📝 Summary

This strategy implements the market making strategy described in the classic paper [High-frequency Trading in a Limit Order Book](https://people.orie.cornell.edu/sfs33/LimitOrderBook.pdf) written by Marco Avellaneda and Sasha Stoikov. It allows users to directly adjust the kappa, gamma, and eta parameters described in the paper. It also features a simplified mode that allows the user to enter min/max spread parameters that continually recalculate the advanced parameters.

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
| `order_amount`               | decimal     |             | True        | What is the amount of `base_asset` per order?|
| `parameters_based_on_spread` | bool        |  True       | True        | Do you want to automate Avellaneda-Stoikov parameters based on min/max spread?|
| `min_spread`                 | decimal     |             | True        | Enter the minimum spread allowed from mid-price in percentage? |
| `max_spread`                 | decimal     |             | True        | Enter the maximum spread allowed from mid-price in percentage? |
| `vol_to_spread_multiplier`   | decimal     |             | True        | Enter the Volatility threshold multiplier: (If market volatility multiplied by this value is above the minimum spread, it will increase the minimum and maximum spread value)|
| `inventory_risk_aversion`    | decimal     |             | True        | Enter Inventory risk aversion between 0 and 1: (For values close to 0.999 spreads will be more skewed to meet the inventory target, while close to 0.001 spreads will be close to symmetrical, increasing profitability but also increasing inventory risk)|
| `order_refresh_time`         | decimal     |             | True        | How often do you want to cancel and replace bids and asks (in seconds)? |
| `inventory_target_base_pct`  | decimal     |  50         | True        | What is the inventory target for the base asset? |
| `order_optimization_enabled` | bool        |  True       | False       | Do you want to enable best bid ask jumping? |
| `volatility_sensibility`     | decimal     |  20         | False       | Enter volatility change threshold to trigger parameter recalculation| 
| `order_book_depth_factor`    | decimal     |  Computed   | False       | Enter order book depth factor (\u03BA)| 
| `risk_factor`                | decimal     |  Computed   | False       | Enter risk factor (\u03B3) |
| `order_amount_shape_factor`  | decimal     |  Computed   | False       | Enter order amount shape factor (\u03B7) |
| `closing_time`               | decimal     |  0.04167    | False       | Enter operational closing time (T). (How long will each trading cycle last in days or fractions of day)|
| `max_order_age`              | decimal     |  1800       | False       | How often do you want to cancel and replace bids and asks (in seconds)? |
| `order_refresh_tolerance_pct`| decimal     |  0          | False       | Enter the percent change in price needed to refresh orders at each cycle |
| `filled_order_delay`         | decimal     |  60         | False       | How long do you want to wait before placing the next order if your order gets filled (in seconds)? |
| `add_transaction_costs`      | decimal     |  False      | False       | Do you want to add transaction costs automatically to order prices? (Yes/No) |
| `volatility_buffer_size`     | decimal     |  1800       | False       | Enter amount of ticks that will be stored to calculate volatility |
| `order_levels`               | int         |  1          | False       | How many orders do you want to place on both sides? |
| `order_override`             | json        |             | False       |  |
| `hanging_orders_enabled`     | bool        |  False      | False       | Do you want to enable hanging orders? (Yes/No) |
| `hanging_orders_cancel_pct`  | decimal     |  10         | False       | At what spread percentage (from mid price) will hanging orders be canceled? |

## 📓 Description

[Trading logic](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/avellaneda_market_making/avellaneda_market_making.pyx)

!!! note "Approximation only"
    The description below is a general approximation of this strategy. Please inspect the strategy code in **Trading Logic** above to understand exactly how it works.

Coming soon.

 <!-- 

### `parameters_based_on_spread`

The parameter acts as a toggle between beginner (parameters_based_on_spread=True) and expert mode (False). When equal to true, the strategy will require min spread, max spread, volatility multiplier, and inventory risk aversion, while if set to False, it will only ask for risk_factor, order_book_depth_factor, and order_amount_shape_factor.


### `vol_to_spread_multiplier`

`vol_to_spread_multiplier` will act as a threshold value to override max_spread when volatility is a higher value. The value should be higher than 1.

### `volatility_sensibility`

The Volatility Sensibility will recalculate `gamma`, `kappa`, and `eta` after the value of volatility sensibility threshold in percentage is achieved. For example, when the parameter is set to 0, it will recalculate `gamma`, `kappa`, and `eta` each time an order is created. The default value for the parameter is 20.

You can visit this introduction and detailed information on this parameter from this [link](https://docs.hummingbot.io/release-notes/0.39.0/) to know more.

### `inventory_risk_aversion`

Inventory Risk Aversion is a quantity between 0 and 1 to measure the compromise between mitigation of inventory risk and profitability. When parameters are closer to 0, spreads will be almost symmetrical. This will tend to generate more profitability. When parameters is closer to 1, will increase chances of one side of bid/ask to be executed with respect to the other, in that way forcing inventory to converge to target while decreasing the final profit.

### **Advanced parameters**

All 3 parameters `order_book_depth_factor`, `risk_factor` and `order_amount_shape_factor` are customizable only in expert mode (toggled by `parameters_based_on_spread`=False).

#### `order_book_depth_factor`

This parameter denoted by the letter **kappa** is directly proportional to the order book's liquidity, hence the probability of an order being filled. For more details, see the foundation paper.

#### `risk_factor`

This parameter, denoted by the letter **gamma**, is related to the aggressiveness when setting the spreads to achieve the inventory target. It is directly proportional to the asymmetry between the bid and ask spread. For more details, see the foundation paper.

### `order_amount_shape_factor`

This parameter denoted in the letter **eta** is related to the aggressiveness when setting the order amount to achieve the inventory target. It is inversely proportional to the asymmetry between the bid and ask order amount. For more details, see the foundation paper.

### `closing_time`

This parameter will be the limit time **T** (measure in days) for this “trading cycle”. We call trading cycles the interval of time where spreads start the widest possible and end up the smallest. Once the cycle is reset, spreads will start again, being the widest possible.

### `volatility_buffer_size`

The number of ticks used as a sample size for volatility calculation.

### `order_levels`

Quantity of orders to be placed on each side of the order book. 

For example, if `order_levels = 2` , it will place **2 Buy Orders & 2 Sell Orders**.

How does it determine order level amounts and spreads? 
-->
