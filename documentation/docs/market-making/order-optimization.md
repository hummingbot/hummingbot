# Order Optimization

**Updated as of `v0.35.0`**

Users now have the option to automatically adjust the prices to the right, just above the top bid and just below the top ask.

!!! note
    `order_optimization_enabled` was previously called `jump_orders_enabled`

## `order_optimization_enabled`

Allows your bid and ask order prices to be adjusted based on the current top bid and ask prices in the market.

** Prompt: **

```json
Do you want to enable best bid ask jumping? (Yes/No)
>>> Yes
```

## `ask_order_optimization_depth`

The depth in base asset amount to be used for finding top ask.

** Prompt: **

```json
How deep do you want to go into the order book for calculating the top ask, ignoring dust orders on the top (expressed in base asset amount)?
>>>
```

## `bid_order_optimization_depth`

The depth in base asset amount to be used for finding the top bid.

** Prompt: **

```json
How deep do you want to go into the order book for calculating the top bid, ignoring dust orders on the top (expressed in base asset amount)?
>>>
```

## How it works

This feature works best in single order mode. Take note that this does not automatically jump your orders from the bottom to the top. Instead, if your orders are already the best in the order book (at the top) this will adjust your prices right next to the next best orders.

It is recommended to disable `add_transaction_costs` (set to `False`) for this feature to work effectively. This is because adding transaction costs would affect the prices at which the orders are placed and might not be the best bid/ask.

## Sample configuration

```json
- bid_spread: 0.1%
- ask_spread: 0.1%
- order_optimization_enabled: false
- ask_order_optimization_depth: 0
- bid_order_optimization_depth: 0
```

Setting our bid and ask threshold to a very small value (0.1%) puts our orders at the top of the order book. For example, the image below shows the buy order is placed at `0.003159` and the sell order at `0.003165` with the order optimization disabled.

![jump_orders_1](/assets/img/jump_orders1.png)

Now let's enable `order_optimization_enabled`. You'll see in the next image that the buy order is placed at `0.003150` and the sell order at `0.003174`, right just above the next best order.

```json
- bid_spread: 0.1%
- ask_spread: 0.1%
- order_optimization_enabled: True
- ask_order_optimization_depth: 0
- bid_order_optimization_depth: 0
```

![jump_orders_2](/assets/img/jump_orders2.png)

If the next best order's price changes (not your own), your existing orders will not adjust immediately. It will wait for `order_refresh_time` to cancel your existing orders and the new orders will try to jump to just above best bid or just below best ask.

## Order optimization depth

This allows users to ignore dust orders specified in the base currency amount. As shown in the example above, this is the expected behavior when enabling order optimization.

```json
- bid_spread: 0.1%
- ask_spread: 0.1%
- order_optimization_enabled: True
- ask_order_optimization_depth: 0
- bid_order_optimization_depth: 0
```

![jump_orders_3](/assets/img/jump_orders3.png)

Here we configure and set `ask_order_optimization_depth` and `bid_order_optimization_depth` both to 5,000.

```json
- bid_spread: 0.1%
- ask_spread: 0.1%
- order_optimization_enabled: True
- ask_order_optimization_depth: 5000
- bid_order_optimization_depth: 5000
```

Doing this ignores the first 5,000 units of orders on each side in the order book and places our orders right next to them.

![jump_orders_4](/assets/img/jump_orders4.png)

## Order optimization with multiple order levels

Users can now use order optimization with multiple `order_levels` see the example below. Order optimization is triggered, and it placed the 2nd order, which has a spread of 0.2% because of `order_level_spread`.

```json
- bid_spread: 0.1%
- ask_spread: 0.2%
- order_levels: 2
- order_level_spread: 0.1%
- order_optimization_enabled: True
- ask_order_optimization_depth: 0
- bid_order_optimization_depth: 0
```

![](/assets/img/multiple_order_levels.png)
