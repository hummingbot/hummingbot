# Order Refresh Tolerance

**Updated as of `v0.27.0`**

This feature allows you to specify a percentage value that sets the minimum change in spread to adjust an order.


## How It Works

By default, this parameter is set to 0 and Hummingbot will cancel outstanding orders except hanging orders every `order_refresh_time` seconds.

As an example, setting `order_refresh_tolerance_pct` to `0.1` and an active order's spread changes from 1.0% to 0.9%-1.1% when it's time to refresh depending on `order_refresh_time`, this order is kept (not cancelled).

## Sample Configuration

```json
- bid_spread: 2.0%
- ask_spread: 2.0%
- order_refresh_time: 30.0
- order_refresh_tolerance_pct: 1%
```

This configuration creates your orders as follows.

```
Orders:                                                               
     Level  Type    Price Spread Amount (Orig)  Amount (Adj)  	   Age Hang
         1  sell 9819.545  2.01%         0.001         0.001  00:00:01   no
         1   buy 9434.465  1.99%         0.001         0.001  00:00:01   no
```

After 30 seconds if the spread of buy/sell order did not change to more than 1% of what it initially was, a message will show in the logs pane.

```
Not cancelling active orders since difference between new order prices
and current order prices is within 1.00% order_refresh_tolerance_pct
```

Now let's say our sell order spread changed from 2.01% to 0.79%. After 30 seconds, it will cancel our orders and create new ones with a 2.0% spread.

```
Orders:                                                               
     Level  Type    Price Spread Amount (Orig)  Amount (Adj)  	   Age Hang
         1  sell 9706.037  0.79%         0.001         0.001  00:00:29   no
         1   buy 9407.538  2.31%         0.001         0.001  00:00:29   no
```

## Relevant Parameters

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **order_refresh_tolerance_pct** | `Enter the percent change in price needed to refresh orders at each cycle` | The spread (from mid price) to defer order refresh process to the next cycle. |