# Hanging Orders

**Updated as of `v0.28.0`**

This feature keeps orders "hanging" (or not cancelled and remaining on the order book) if a matching order has been filled on the other side of the order book (bid vs. ask order books).

## How It Works

Typically, orders are placed as pairs in single order mode (1 buy and 1 sell order), and when a buy or sell order is filled, the other order is cancelled. The parameter `hanging_orders_enabled` allows Hummingbot to leave the order on the other side hanging (not cancelled) whenever one side is filled.

The hanging order will be cancelled in the following conditions:

1. The spread goes above the specified `hanging_orders_cancel_pct` value
2. Sending `stop` or `exit` command

Type `config hanging_orders_enabled` and `config hanging_orders_cancel_pct` to set values for these parameters. 

## Illustrative Examples - When Hanging Orders are Important

###Example 1 (Basic)

Suppose you are market making for the `ETH-USDT` pair with a mid-market price of 200 USD ($t_0$). You set your bid spread and ask spread to 1%. Thus, the bid price is 198 USD and the ask price is 202 USD. 

Now suppose that a market taker (someone taking a position in the market) thinks the price of Ethereum will rise, so they fill your ask order 202 ($t_1$). 

At the next order refresh cycle, normally Hummingbot would cancel the 198 USD bid order and create 2 new bid and ask orders. However, if `hanging_orders_enabled` is set to True, the bid order is not cancelled and stays on the order book until it is filled. Note that if an open hanging order spread exceeds the `hanging_orders_cancel_pct` parameter, the hanging order will be canceled.

###Example 2 (Advanced)

Suppose that you are again market making for `ETH-USDT` pair. The bid and ask spread is set to 1%. Consider the two strategies below, the former the default and the latter with hanging orders. The white line in the center is the mid market price in USDT; The dashed lines above the mid-market price are the active ask-orders; And the dotted lines below the mid-market price are the active bid-orders.

####Market *Without* Hanging Orders

![Advanced Market With No Hang](/assets/img/hanging_orders_example_market_adv_no_hang.png)

In this strategy, the `hanging_orders_enabled` parameter is False. At each interval $t_i$, the order is either cancelled or filled, then refreshed with a new set of bid and ask orders (each with a 1% spread from the mid-market price). There are only two orders at a time, an ask order and a bid order. This is a great strategy as a default, however, price takers need to be willing to fill orders relatively close to your chosen spread. It may require you to tighten your spread to get more price takers to fill your orders. 

####Market *With* Hanging Orders
![Advanced Market With Hanging Orders](/assets/img/hanging_orders_example_market_adv_with_hang.png)

In this strategy, the `hanging_orders_enabled` parameter is True. We set the `hanging_orders_cancel_pct` parameter to 2% and make the assumption that an order is filled by a market-taker if the spread is within 0.55%. When a bid order is filled or canceled, unlike the default, the ask order is left open. Similarly, when a ask order is filled or cancelled, the bid order is left open. As you can see above, from $t_0$ to $t_{10}$ generally the bid orders are "hanging" until their spreads are greater than 2% from the mid-market price line (or are filled). From $t_0$ to $t_{10}$, the ask orders are being filled as they fall within 0.55% of spread to the mid-market price line. The opposite is true from $t_{10}$ to $t_{20}$, where bid orders are being filled as they fall within 0.55% of the spread to the mid-market price line and the ask orders are "hanging" until they are cancelled when their spreads are greater than 2%. 

This strategy allows for a range of spreads between the cancel percentage parameter and when a price taker fills your order (presumably when the order price is closer to the mid-market price). It is ultimately a more flexible strategy and can capture profitable trades that are lost without hanging orders. For example, in the Sample Markets above, the purple bid order starting at $t_8$ is lost without allowing it to be a hanging order, whereas in the second chart, the bid order is filled at $t_{13}$.

## Sample Configurations

Let's see how this configuration works in the scenario below:

```json
- filled_order_delay: 60.0
- hanging_orders_enabled: True
- hanging_orders_cancel_pct: 2
```

![](/assets/img/hanging_order2.png)

When the buy order was completely filled, it will not cancel the sell order. After 60 seconds, Hummingbot will create a new set of buy and sell orders. The `status` output will show all active orders while indicating which orders are hanging.

![](/assets/img/hanging_order3.png)

The hanging order will stay outstanding and will be cancelled if its spread goes above 2% as specified in our `hanging_orders_cancel_pct`.

![](/assets/img/hanging_order4.png)

## Hanging Orders with Multiple Order Levels

When an order is filled on one side either buy or sell, all active orders on the opposite side are left hanging.

```json
- hanging_orders_enabled: True
- order_levels: 3
```

With the sample configuration above, the bot places 3 buy and 3 sell orders.

```
Orders:                                                                
   Level  Type  Price Spread Amount (Orig)  Amount (Adj)       Age Hang
       3  sell 239.75  2.49%          0.05          0.05  00:00:01   no
       2  sell 237.41  1.49%          0.05          0.05  00:00:01   no
       1  sell 235.07  0.49%          0.05          0.05  00:00:01   no
       1   buy  233.9  0.01%          0.05          0.05  00:00:01   no
       2   buy 231.56  1.01%          0.05          0.05  00:00:01   no
       3   buy 229.22  2.01%          0.05          0.05  00:00:01   no
```

Buy order 1 gets filled.

```
Maker BUY order 0.05000000 ETH @ 233.90000000 USDT is filled.  
```

This leaves the 3 sell orders hanging on top of the new orders on the next refresh.

```
Orders:                                                               
  Level  Type  Price Spread Amount (Orig)  Amount (Adj)       Age Hang
         sell 239.75  2.50%                        0.05  00:01:08  yes
      3  sell 239.73  2.49%          0.05          0.05  00:00:01   no
         sell 237.41  1.50%                        0.05  00:01:08  yes
      2  sell 237.39  1.49%          0.05          0.05  00:00:01   no
         sell 235.07  0.50%                        0.05  00:01:08  yes
      1  sell 235.05  0.49%          0.05          0.05  00:00:01   no
      1   buy 233.88  0.01%          0.05          0.05  00:00:01   no
      2   buy 231.54  1.01%          0.05          0.05  00:00:01   no
      3   buy  229.2  2.01%          0.05          0.05  00:00:01   no

```


## Relevant Parameters

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **hanging_orders_enabled** | `Do you want to enable hanging orders? (Yes/No)` | When enabled, the orders on the side opposite to the filled orders remains active. |
| **hanging_orders_cancel_pct** | `At what spread percentage (from mid price) will hanging orders be canceled?` | Cancels the hanging orders when their spread goes above this value. |
