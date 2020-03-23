# Best Bid Ask Jumping

Users now have the option to automatically adjust the prices to just above top bid and just below top ask using `best_bid_ask_jump_mode` available in single order mode. It can also be specified how deep to go into the orderbook for calculating the top bid and top ask price using `best_bid_ask_jump_orders_depth`.

It is recommended to disable `add_transaction_costs` (set to `false`) for penny jumping mode to work effectively. This is because adding transaction costs would affect the prices at which the orders are placed and they might not be at the best bid/ask.

**Example scenario:**

The top bid/ask in the orderbook is 98 and 102 respectively and the mid price is 100.

Below is a sample configuration:

```
mode = single
order size = 1
bid threshold = 0.01 (1%)
ask threshold = 0.01 (1%)
best_bid_ask_jump_mode = true
jump_order_depth = 0
add_transaction_costs = false
```

Using the configs above, Hummingbot should place a buy order at 99 and sell order at 101. However, since penny jumping mode is enabled it will create orders with prices right just above the current top bid/ask in the orderbook. Hummingbot will place the buy order at 98.001 and the sell order at 101.999 instead. This will allow the user to capture a higher spread than the specified bid/ask threshold while keeping your orders at the top.

**Example 2:**

You have set your bid and ask threshold to a very small value that it puts your orders at the top of the order book. The image on the left shows the buy order is placed at `0.003159` and the sell order at `0.003165` with best bid ask jump mode disabled.

The image on the right has best bid ask jump enabled which places the buy order at `0.003150` and sell order at `0.003174` right just above the next best order.

![jump_orders_1](/assets/img/jump_orders1.png)
![jump_orders_2](/assets/img/jump_orders2.png)


When the next best order's price changes (not your own), your existing orders will not jump immediately. It will wait till `cancel_order_wait_time` for the orders to get cancelled and the new order will try to jump to just above best bid or just below best ask.


| Prompt | Description |
|-----|-----|
| `Do you want to enable best bid ask jumping? (Yes/No) >>>` | This sets `best_bid_ask_jump_mode` ([definition](#configuration-parameters)). |
| `How deep do you want to go into the order book for calculating the top bid and ask, ignoring dust orders on the top (expressed in base asset amount)? >>>` | This sets `best_bid_ask_jump_orders_depth` ([definition](#configuration-parameters)). |

