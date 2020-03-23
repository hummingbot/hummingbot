# Best Bid Ask Jumping

Users now have the option to automatically adjust the prices to right just above the top bid and just below the top ask.

## How It Works

This feature works best in single order mode. Take note that this does not automatically jump your orders from the bottom to the top. Instead, if your orders are already the best in the orderbook (at the top) this will adjust your prices right next to the next best orders.

It is recommended to disable `add_transaction_costs` (set to `false`) for this feature to work effectively. This is because adding transaction costs would affect the prices at which the orders are placed and they might not be at the best bid/ask.

## Sample Configuration


```json
- bid threshold: 0.001 (0.1%)
- ask threshold: 0.001 (0.1%)
- best_bid_ask_jump_mode: false
```

Setting our bid and ask threshold to a very small value (0.1%) puts our orders at the top of the order book. The image on below shows the buy order is placed at `0.003159` and the sell order at `0.003165` with best bid ask jump mode disabled.

![jump_orders_1](/assets/img/jump_orders1.png)

The image on the right has best bid ask jump enabled which places the buy order at `0.003150` and sell order at `0.003174` right just above the next best order.

Now let's enable `best_bid_ask_jump_mode`. You'll see in the next image that the buy order is placed at `0.003150` and sell order at `0.003174` right just above the next best order.

```json
- bid threshold: 0.001 (0.1%)
- ask threshold: 0.001 (0.1%)
- best_bid_ask_jump_mode: true
```

![jump_orders_2](/assets/img/jump_orders2.png)


If the next best order's price changes (not your own), your existing orders will not jump immediately. It will wait for `cancel_order_wait_time` to cancel your existing orders and the new orders will try to jump to just above best bid or just below best ask.


## Relevant Parameters

| Parameter | Prompt | Definition | Default Value |
|-----------|--------|------------|---------------|
| **best_bid_ask_jump_mode** | `Do you want to enable best bid ask jumping? (Yes/No) >>>` | Allows your bid and ask order prices to be adjusted based on the current top bid and ask prices in the market. | `false` |
| **best_bid_ask_jump_orders_depth** | `How deep do you want to go into the order book for calculating the top bid and ask, ignoring dust orders on the top (expressed in base asset amount)? >>>` | The depth in base asset amount to be used for finding top bid and ask. | `0.0` |

