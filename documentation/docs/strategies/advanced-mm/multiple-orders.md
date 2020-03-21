# Multiple Order Configuration

These parameters allow you to set multiple levels of orders on each side and gives you more fine-grained control over the spreads and sizes of each set of orders.

## How It Works

## Configuration Walkthrough

| Prompt | Description |
|-----|-----|
| `How many orders do you want to place on both sides? >>>` | This sets `number_of_orders` ([definition](#configuration-parameters)). |
| `What is the size of the first bid and ask order? >>>` | This sets `order_start_size` ([definition](#configuration-parameters)). |
| `How much do you want to increase the order size for each additional order? >>>` | This sets `order_step_size` ([definition](#configuration-parameters)). |
| `Enter the price increments (as percentage) for subsequent orders? (Enter 0.01 to indicate 1%) >>>` | This sets `order_interval_percent` ([definition](#configuration-parameters)). |

!!! Note "Order Interval Percent"
    Setting `order_interval_percent` to a very low number may cause multiple orders to be placed on the same price level. For example for an asset like SNM/BTC, if you set an order interval percent of 0.004 (~0.4%) because of low asset value the price of the next order will be rounded to the nearest price supported by the exchange, which in this case might lead to multiple orders being placed at the same price level.


## Configuration Parameters
