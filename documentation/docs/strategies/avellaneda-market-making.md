# Avellaneda Market Making

!!! warning
    This experimental strategy has undergone code review, internal testing and was shipped during one of our most recent releases. As part of User Acceptance Testing, we encourage the user to report any issues and/or provide feedback with this strategy in our [Discord server](https://discord.com/invite/2MN3UWg) or [submit a bug report](https://github.com/CoinAlpha/hummingbot/issues/new?assignees=&labels=bug&template=bug_report.md&title=)

## How it works

The Avellaneda Market Making Strategy is designed to scale inventory and keep it at a specific target that a user defines it with. To achieve this, the strategy will optimize both bid and ask spreads and their order amount to maximize profitability.

In its beginner mode, the user will be asked to enter min and max spread limits, and it's aversion to inventory risk scaled from 0 to 1 (Being 0 more driven to profit but less to inventory in target, and 1 being driven to keep tight control of inventory at the expense of less profit). Additionally, sensitivity to volatility changes will be included with a particular parameter `vol_to_spread_multiplier`, to modify spreads in big volatility scenarios.

In expert mode, the user will need to directly define the algorithm's basic parameters described in the [foundation paper](https://people.orie.cornell.edu/sfs33/LimitOrderBook.pdf), and no recalculation of parameters will happen.

## Prerequisites

### Inventory

You will need to hold a sufficient inventory of quote and or base currencies on the exchange to place orders of the exchange's minimum order size.

### Minimum order size

When placing orders, if the order's size determined by the order price and quantity is below the exchange's minimum order size, then the orders will not be created.

## Basic parameters

We aim to teach new users the basics of market-making while enabling experienced users to exercise more control over how their bots behave. By default, when you run `create,` we ask you to enter the basic parameters needed for a market-making bot.

### `exchange`

The exchange where the bot will place the bid and ask orders.

** Prompt: **

```json
Enter your maker spot connector
>>> binance
```

### `market`

Token trading pair symbol you would like to trade on the exchange.

** Prompt: **

```json
Enter the token trading pair you would like to trade on the exchange
>>> BTC-USDT
```

### `order_amount`

The order amount for the limit bid and ask orders. Ensure you have enough quote and base tokens to place the bid and ask for orders. The strategy will not place any orders if you do not have sufficient balance on either side of the order.

** Prompt: **

```json
What is the amount of [base_asset] per order? (minimum [min_amount])
>>>
```

### `parameters_based_on_spread`

The parameter acts as a toggle between beginner (parameters_based_on_spread=True) and expert mode (False). When equal to true, the strategy will require min spread, max spread, volatility multiplier, and inventory risk aversion, while if set to False, it will only ask for risk_factor, order_book_depth_factor, and order_amount_shape_factor.

** Prompt: **

```json
Do you want to automate Avellaneda-Stoikov parameters based on min/max spread?
>>> True
```

### `min_spread`

The minimum spread related to the mid-price allowed by the user for bid/ask orders.

** Prompt: **

```json
Enter the minimum spread allowed from mid-price in percentage (Enter 1 to indicate 1%)
>>>
```

### `max_spread`

The maximum spread related to the mid price allowed by user for bid/ask orders

** Prompt: **

```json
Enter the maximum spread allowed from mid-price in percentage (Enter 1 to indicate 1%)
>>>
```

### `vol_to_spread_multiplier`

`vol_to_spread_multiplier` will act as a threshold value to override max_spread when volatility is a higher value. The value should be higher than 1.

** Prompt: **

```json
Enter the Volatility threshold multiplier: (If market volatility multiplied by this value is above maximum spread, it will increase the maximum spread value)
>>>
```

### `volatility_sensibility`

The Volatility Sensibility will recalculate `gamma`, `kappa`, and `eta` after the value of volatility sensibility threshold in percentage is achieved. For example, when the parameter is set to 0, it will recalculate `gamma`, `kappa`, and `eta` each time an order is created. The default value for the parameter is 20.

You can visit this introduction and detailed information on this parameter from this [link](https://docs.hummingbot.io/release-notes/0.39.0/) to know more.

** Prompt: **

```json
Enter volatility change threshold to trigger parameter recalculation
>>> 20
```

### `inventory_risk_aversion`

Inventory Risk Aversion is a quantity between 0 and 1 to measure the compromise between mitigation of inventory risk and profitability. When parameters are closer to 0, spreads will be almost symmetrical. This will tend to generate more profitability. When parameters is closer to 1, will increase chances of one side of bid/ask to be executed with respect to the other, in that way forcing inventory to converge to target while decreasing the final profit.

** Prompt: **

```json
Enter Inventory risk aversion between 0 and 1: (For values close to 0.999 spreads will be more skewed to meet the inventory target, while close to 0.001 spreads will be close to symmetrical, increasing profitability but also increasing inventory risk)
>>>
```

### `order_refresh_time`

An amount in seconds, which is the duration for the placed limit orders. The limit bid and ask orders are canceled, and new orders are placed according to the current mid-price and spread at this interval.

** Prompt: **

```json
How often do you want to cancel and replace bids and asks (in seconds)?
>>>
```

### `inventory_target_base_pct`

It sets a target of base asset balance in relation to a total asset allocation value (in percentage value). It works the same as the pure market making strategy's [inventory_skew](/strategies/inventory-skew/) feature in order to achieve this target.

** Prompt: **

```json
What is your inventory target for base asset? Enter 50 for 50%?
>>> 50
```

## Advanced parameters

These are additional parameters that you can reconfigure and use to customize the behavior of your strategy further. To change its settings, run the command `config` followed by the parameter name, e.g. `config max_order_age`.

All 3 parameters ‘order_book_depth_factor’, ‘risk_factor’ and ‘order_amount_shape_factor’ are customizable only in expert mode (toggled by ‘parameters_based_on_spread’=False).

### `order_book_depth_factor`

This parameter denoted by the letter kappa is directly proportional to the order book's liquidity, hence the probability of an order being filled. For more details, see the foundation paper.

** Prompt: **

```json
Enter order book depth factor (k)
>>>
```

### `risk_factor`

This parameter, denoted by the letter gamma, is related to the aggressiveness when setting the spreads to achieve the inventory target. It is directly proportional to the asymmetry between the bid and ask spread. For more details, see the foundation paper.

** Prompt: **

```json
Enter risk factor (y)
>>>
```

### `order_amount_shape_factor`

This parameter denoted in the letter eta is related to the aggressiveness when setting the order amount to achieve the inventory target. It is inversely proportional to the asymmetry between the bid and ask order amount. For more details, see the foundation paper.

** Prompt: **

```json
Enter order amount shape factor (n)
>>>
```

### `closing_time`

This parameter will be the limit time (measure in days) for this “trading cycle”. We call trading cycles the interval of time where spreads start the widest possible and end up the smallest. Once the cycle is reset, spreads will start again, being the widest possible.

** Prompt: **

```json
Enter operational closing time (T). (How long will each trading cycle last in days or fractions of day)
>>>
```

### `order_optimization_enabled`

Allows your bid and ask order prices to be adjusted based on the current top bid and ask prices in the market. By default, this parameter is set to True.

** Prompt: **

```json
Do you want to enable best bid ask jumping? (Yes/No)
>>>
```

### `max_order_age`

The `max_order_age` parameter allows you to set a specific duration when resetting your order's age. It refreshes your orders and automatically creates an order based on the spread and movement of the market.

** Prompt: **

```json
How long do you want to cancel and replace bids and asks with the same price (in seconds)?
>>>
```

### `order_refresh_tolerance_pct`

The spread (from mid-price) to defer the order refresh process to the next cycle.

To know more about this parameter you can visit this [link](https://docs.hummingbot.io/strategies/order-refresh-tolerance/#gatsby-focus-wrapper)

** Prompt: **

```json
Enter the percent change in price needed to refresh orders at each cycle
>>> 1
```

### `filled_order_delay`

How long to wait before placing the next set of orders in the case at least one of your orders gets filled.

For example, with a filled_order_delay = 300 when an order created by the bot is filled, the next pair of orders will only be created 300 seconds later.

** Prompt: **

```json
How long do you want to wait before placing the next order if your order gets filled (in seconds)?
>>>
```

### `add_transaction_costs`

Whether to enable adding transaction costs to order price calculation.

** Prompt: **

```json
Do you want to add transaction costs automatically to order prices? (Yes/No)
>>>
```

### `volatility_buffer_size`

The number of ticks used as a sample size for volatility calculation.

** Prompt: **

```json
Enter amount of ticks that will be stored to calculate volatility
>>>
```

### `order_levels`

Quantity of orders to be placed on each side of the order book.

For example, if `order_levels = 2` , it will place **2 Buy Orders & 2 Sell Orders**.

** Prompt: **

```json
How many orders do you want to place on both sides?
>>>
```

### `order_override`

Directly override orders placed by `order_amount` and `order_level_parameter`.

To start this override feature, users must input the parameters manually in the strategy config file they intend to use. Learn how to access config files with this [documentation](/operation/config-files).

Below is a sample input in dictionary format.

The key is a user-defined order name and the value is a list which includes **buy/sell, order spread, and order amount**:

```
order_override:
  order_1: [buy, 0.5, 100]
  order_2: [buy, 0.75, 200]
  order_3: [sell, 0.1, 500]

  # Please make sure there is a space between : and [
  # order_1 label can be renamed to custom labels
```

## Hanging orders

An Avellaneda strategy feature that recalculates your hanging orders with aggregation of volume weighted, volume time weighted, and volume distance weighted.

`config hanging_orders_enabled`

![hanging orders enabled](/assets/img/AvellanedaHangingOrders_Enable.gif)

`config hanging_orders_aggregation_type`

![hanging orders aggregate](/assets/img/AvellanedaHangingOrders_Aggregate.gif)

`config hanging_orders_cancel_pct`

![hanging orders cancel pct](/assets/img/AvellanedaHangingOrders_cancel_pct.gif)

Adjust the settings by opening the strategy config file with a text editor.

```
# Whether to stop cancellations of orders on the other side (of the order book),
# when one side is filled (hanging orders feature) (true/false).
hanging_orders_enabled: true

# Select way of aggregating hanging orders. Whether if leaving them as they are or calculating a resulting hanging order
# default = no_aggregation, volume_weighted, volume_time_weighted, volume_distance_weighted

hanging_orders_aggregation_type: volume_weighted

# Spread (from mid price, in percentage) hanging orders will be canceled (Enter 1 to indicate 1%)
hanging_orders_cancel_pct: .5
```
