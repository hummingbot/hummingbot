# Multiple Orders

These parameters allow you to set multiple levels of orders on each side and gives you more fine-grained control over the spreads and sizes of each set of orders.

## How It Works

![Market making with 3 order levels for BTC-USDT](/assets/img/multiple-orders.png)

For example, the screenshot of the `status` command above shows 3 levels of orders in the BTC-USDT trading pair. Below are the parameters used:
```json
- maker_market_trading_pair: BTC-USDT
- mode: multiple
- number_of_orders: 3
- order_start_size: 0.002
- order_step_size: 0.002
- ask_place_threshold: 0.005
- bid_place_threshold: 0.005
- order_interval_percent: 0.01
```

## Relevant Parameters

| Parameter / Prompt | Definition | Default Value |
|--------------------|------------|---------------|
| **number\_of\_orders**<br/>`How many orders do you want to place on both sides? >>>` | The number of order levels to place for each side of the order book.<br/><br/>*Example: Entering `3` places three bid and three ask orders on each side of the book, for a total of 6 orders.* | `1` |
| **order\_start\_size**<br/>`What is the size of the first bid and ask order? >>>` | The size of the first order level, in base asset units | none |
| **order\_step\_size**<br/>`How much do you want to increase the order size for each additional order? >>>` | The incremental size increase for subsequent order levels after the first level.<br/><br/>*Example: Entering `1` when the first order size is `10` results in sizes of `11` and `12` for the second and third order levels* | `0` |
| **order\_interval\_percent**<br />`Enter the price increments (as percentage) for subsequent orders? (Enter 0.01 to indicate 1%) >>>` | The incremental spread increases for subsequent order levels after the first level.<br/><br/>*Example: Entering `0.005` when ask and bid spreads are `0.01` results in the spreads of `0.015` amd `0.025` for the second and third order levels.* | `0` |

!!! warning "Low values for `order_interval_percent`"
    Setting `order_interval_percent` to a very low number may cause multiple orders to be placed on the same price level. For example for an asset like SNM/BTC, if you set an order interval percent of 0.004 (~0.4%) because of low asset value the price of the next order will be rounded to the nearest price supported by the exchange, which in this case might lead to multiple orders being placed at the same price level.