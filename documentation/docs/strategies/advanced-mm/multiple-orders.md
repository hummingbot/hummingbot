# Multiple Orders

These parameters allow you to set multiple levels of orders on each side and gives you more fine-grained control over the spreads and sizes of each set of orders.

## How It Works

Enter the value for `order_levels` to specify how many orders you want to place on each side (buy and sell).

>**Example**: Entering `3` places three bid and three ask orders on each side of the book, for a total of 6 orders.

Users can also increase the size of subsequent orders starting from the first order in increments specified in `order_level_amount`. This can be set to `0` if you don't want your multiple order sizes to increase.

>**Example**: If the order start size is `7000` and the order step size is `1000`, the second order size is `8000`, and the third order is `9000`.

The `order_level_spread` logic works the same as order step size but instead, it increases the spreads of your subsequent orders starting from the first order.

>**Example**: The spread of your first buy and sell order is `0.01` (1%) and your order interval amount is `0.02` (2%). The spread of your second order is `0.03` (3%), and the third order is `0.05` (5%).

Given the sample scenarios above, your active orders will show as:

![](/assets/img/multiple_orders1.png)


## Sample Configuration

```json
- market: BTC-USDT
- bid_spread: 0.005
- ask_spread: 0.005
- order_amount: 0.002
- order_levels: 3
- order_levels_amount: 0.002
- order_levels_spread: 0.01
```

Running a bot with the parameters above, the `status` command shows 3 levels of orders in the BTC-USDT trading pair: 
![Market making with 3 order levels for BTC-USDT](/assets/img/multiple-orders.png)


## Relevant Parameters

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **order_levels** | `How many orders do you want to place on both sides?` | The number of order levels to place for each side of the order book. |
| **order_level_amount** | `How much do you want to increase the order size for each additional order?` | The incremental size increase for subsequent order levels after the first level. |
| **order_level_spread** | `Enter the price increments (as percentage) for subsequent orders?` | The incremental spread increases for subsequent order levels after the first level. |

!!! warning "Low values for `order_level_spread`"
    Setting `order_level_spread` to a very low number may cause multiple orders to be placed on the same price level. For example for an asset like SNM/BTC, if you set an order interval percent of 0.004 (~0.4%) because of low asset value the price of the next order will be rounded to the nearest price supported by the exchange, which in this case might lead to multiple orders being placed at the same price level.