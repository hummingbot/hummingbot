# Order Refresh Tolerance

**Updated as of `v0.28.0`**

This feature allows you to specify a range of spreads that is "tolerable" - not cancelled and left on the order books - every refresh cycle. It allows you to specify the allowed minimum percentage change in spread to adjust an order. If there is movement in the mid-market price, you can create flexibility with your trading strategy to control when orders are canceled/replaced (refreshed) with a tolerance percent change to capture additional profit (see [How Is This Parameter Helpful](./#how-is-this-parameter-helpful) below). 



## How It Works
Type `config order_refresh_tolerance_pct` to set this parameter. By default, this parameter is set to `0`. 

This means that Hummingbot will cancel active orders (excluding hanging orders) every `order_refresh_time` seconds. However, if the price has not changed since the last cycle, Hummingbot will leave the orders there. Setting it to `-1` will disable the feature, which means Hummingbot will always cancel and create orders every `order_refresh_time` seconds.

For example, setting `order_refresh_tolerance_pct` to `0.1` and an active order's spread changes from 1.0% to 0.9%-1.1% when it's time to refresh depending on `order_refresh_time`, this order is kept on the order books (not cancelled). If the spread exceeds 1.1% or goes below 0.9%, then the order is cancelled.

Note that one can set `order_refresh_tolerance_pct` to be greater than the bid and ask spreads. If so, the spread can be negative and put you in a **position of loss**.

## Example
Imagine you are trading the `ETH-USDT` asset pair on an exchange with a starting mid-market price of 200 USDT ($t_0$). 

###Sample Market
![Sample Market: ETH-USDT](/assets/img/order_refresh_tolerance_sample_market.png)

###Configuration
```json
- bid_spread: 2
- ask_spread: 2
- order_refresh_time: 30.0
- order_refresh_tolerance_pct: 1
```

### Sample Status Output/Log

The ask and bid spread is 2%, so your bot will place orders at the ask price of 204 and your bid price to 196 ($t_1$). This configuration creates your orders as follows.

```
Orders:                                                               
     Level  Type    Price Spread Amount (Orig)  Amount (Adj)  	   Age Hang
         1  sell      204  2.00%         0.001         0.001  00:00:01   no
         1   buy      196  2.00%         0.001         0.001  00:00:01   no
```

Every 30 seconds, the bot will only cancel and replace the orders if the spreads exceed the range of 1% - 3%.

After 30 seconds ($t_2$), the mid-market price increases to 201; the sell spread is 1.49% and the buy spread is 2.49%. The status of the orders is follows:
```
Orders:                                                               
     Level  Type    Price Spread Amount (Orig)  Amount (Adj)  	   Age Hang
         1  sell      204  1.49%         0.001         0.001  00:00:29   no
         1   buy      196  2.49%         0.001         0.001  00:00:29   no
```

The spread of buy/sell order did not change by more than 1% of what it initially was, a message will show in the logs pane.

```
Not cancelling active orders since difference between new order prices
and current order prices is within 1.00% order_refresh_tolerance_pct
```

Let's say a market taker, someone taking a position in the market, likes the smaller sell spread of right before $t_3$ before the ask spread reaches 0.99% (lets say around 1%)  and decides to fill your sell order because they think the market price will go up. At $t_3$, the bot cancels the buy order and creates two new orders with a ask and buy spread of 2%.

```
Orders:                                                               
     Level  Type    Price Spread Amount (Orig)  Amount (Adj)  	   Age Hang
         1  sell   205.02  2.00%         0.001         0.001  00:00:01   no
         1   buy   196.98  2.00%         0.001         0.001  00:00:01   no
```

Consider now that at $t_4$ the price drops to 199. The bid spread is 1.01% and the ask spread is 3.02%. This is outside of the order refresh tolerance because the spread has changed by more than 1%. 


The bot cancels both orders and replaces them with a spread of 2%, lets say at $t_5$.

```
Orders:                                                               
     Level  Type    Price Spread Amount (Orig)  Amount (Adj)  	   Age Hang
         1  sell   202.98  2.00%         0.001         0.001  00:00:01   no
         1   buy   195.02  2.00%         0.001         0.001  00:00:01   no
```

Now, at $t_6$ the spread is now 1.5% and 2.5% for bid and ask spreads, respectively. 

```
Orders:                                                               
     Level  Type    Price Spread Amount (Orig)  Amount (Adj)  	   Age Hang
         1  sell   202.98  2.52%         0.001         0.001  00:00:29   no
         1   buy   195.02  1.51%         0.001         0.001  00:00:29   no
```

The bot will leave these orders because they are within the order refresh tolerance and display the following message again:
```
Not cancelling active orders since difference between new order prices
and current order prices is within 1.00% order_refresh_tolerance_pct
```
Lets say that a market taker thinks the market price will decrease substantially and likes your bid-spread. They then can fill your buy order at 195.02.

## How Is This Parameter Helpful

The default for this parameter is a tolerance of 0%. Thus, at each refresh cycle, if the spreads changes *at all*, then the bot will cancel the orders and place new orders at the configuration spread. Because the spread resets at every refresh cycle, this increases the likelyhood that the bid and ask spread are closer to the original bid and ask spread. This reduces the risk that the spread substantially strays away from the original spread, perhaps preventing a loss. *However*, as we have seen above, the strategy can capitalize on the flexibility (tolerance) of the bid and ask spreads because price takers could be looking for some range of spreads that is unknown to you.

## Relevant Parameters

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **order_refresh_tolerance_pct** | `Enter the percent change in price needed to refresh orders at each cycle` | The spread (from mid price) to defer order refresh process to the next cycle. |