# Order Optimization

Users now have the option to automatically adjust the prices to right just above the top bid and just below the top ask.

## How It Works

This feature works best in single order mode. Take note that this does not automatically jump your orders from the bottom to the top. Instead, if your orders are already the best in the orderbook (at the top) this will adjust your prices right next to the next best orders.

It is recommended to disable `add_transaction_costs` (set to `False`) for this feature to work effectively. This is because adding transaction costs would affect the prices at which the orders are placed and they might not be at the best bid/ask.

## Sample Configuration

```json
- bid_spread: 0.1%
- ask_spread: 0.1%
- order_optimization_enabled: false
- ask_order_optimization_depth: 0
- bid_order_optimization_depth: 0
```

Setting our bid and ask threshold to a very small value (0.1%) puts our orders at the top of the order book. The image on below shows the buy order is placed at `0.003159` and the sell order at `0.003165` with best bid ask jump mode disabled.

![jump_orders_1](/assets/img/jump_orders1.png)

Now let's enable `order_optimization_enabled`. You'll see in the next image that the buy order is placed at `0.003150` and sell order at `0.003174` right just above the next best order.

```json
- bid_spread: 0.1%
- ask_spread: 0.1%
- order_optimization_enabled: True
- ask_order_optimization_depth: 0
- bid_order_optimization_depth: 0
```

![jump_orders_2](/assets/img/jump_orders2.png)

If the next best order's price changes (not your own), your existing orders will not adjust immediately. It will wait for `order_refresh_time` to cancel your existing orders and the new orders will try to jump to just above best bid or just below best ask.

## Order Optimization Depth

This allows users to ignore dust orders specified in base currency amount. As shown in the example above, this is the normal behavior when enabling order optimization.

```json
- bid_spread: 0.1%
- ask_spread: 0.1%
- order_optimization_enabled: True
- ask_order_optimization_depth: 0
- bid_order_optimization_depth: 0
```

![jump_orders_3](/assets/img/jump_orders3.png)

Then we reconfigure and set `ask_order_optimization_depth` and `bid_order_optimization_depth` both to 50,000.

```json
- bid_spread: 0.1%
- ask_spread: 0.1%
- order_optimization_enabled: True
- ask_order_optimization_depth: 50000
- bid_order_optimization_depth: 50000
```

Doing this ignores the first 50,000 units of orders on each side in the orderbook and places our orders right next to them.

![jump_orders_4](/assets/img/jump_orders4.png)


Setting a very high optimization depth with your current minimum spread pushes your spread far away from mid price.

```json
- bid_spread: 1.1%
- ask_spread: 1.1%
- minimum_spread: 1
- order_optimization_enabled: True
- ask_order_optimization_depth: 500
- bid_order_optimization_depth: 500
```

With the scenerio above, optimization depth set to 500 base asset amount. It will push the spread far away from mid price then depending on the market and because the optimization depth is set very high the orders spread will push very far from the mid price then orders will cancelled on the next tick.

```
21:52:03 - Created LIMIT_MAKER BUY order x-XEKWYICX-BEHBC1598881921169224 for 0.03000000 ETHBTC.
21:52:03 - Created LIMIT_MAKER SELL order x-XEKWYICX-SEHBC1598881921170200 for 0.03000000 ETHBTC.
21:52:04 - Successfully cancelled order x-XEKWYICX-BEHBC1598881921169224.
21:52:04 - Successfully cancelled order x-XEKWYICX-SEHBC1598881921170200.
21:52:05 - (ETHBTC) Creating 1 bid orders at (Size, Price): ['0.03 ETH, 0.037045 BTC']
21:52:05 - (ETHBTC) Creating 1 ask orders at (Size, Price): ['0.03 ETH, 0.037085 BTC']
21:52:05 - Created LIMIT_MAKER BUY order x-XEKWYICX-BEHBC1598881925061519 for 0.03000000 ETHBTC.
21:52:06 - (ETHBTC) Cancelling the limit order x-XEKWYICX-BEHBC1598881925061519. [clock=2020-08-31 13:52:06+00:00]
21:52:06 - (ETHBTC) Cancelling the limit order x-XEKWYICX-SEHBC1598881925062492. [clock=2020-08-31 13:52:06+00:00]
21:52:06 - Created LIMIT_MAKER SELL order x-XEKWYICX-SEHBC1598881925062492 for 0.03000000 ETHBTC.
21:52:06 - Successfully cancelled order x-XEKWYICX-BEHBC1598881925061519.
21:52:07 - Successfully cancelled order x-XEKWYICX-SEHBC1598881925062492.
```


## Relevant Parameters

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **order_optimization_enabled** | `Do you want to enable best bid ask jumping? (Yes/No)` | Allows your bid and ask order prices to be adjusted based on the current top bid and ask prices in the market. |
| **ask_order_optimization_depth** | `How deep do you want to go into the order book for calculating the top ask, ignoring dust orders on the top (expressed in base asset amount)?` | The depth in base asset amount to be used for finding top bid ask. |
| **bid_order_optimization_depth** | `How deep do you want to go into the order book for calculating the top bid, ignoring dust orders on the top (expressed in base asset amount)?` | The depth in base asset amount to be used for finding top bid. |
