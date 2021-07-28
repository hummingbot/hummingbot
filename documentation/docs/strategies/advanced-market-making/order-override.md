# Order Override

This feature allows users to customize and specify how Hummingbot creates orders in terms of order levels, spread, and size.


## How It Works

Since this is a feature designed for advanced users, it is not configurable from the Hummingbot client. Follow the steps below to set up `order_override` parameter:

1. Edit the strategy config file located in the Hummingbot `conf` folder using a text editor.</br>See [Where are my config and log files?](faq/troubleshooting/#where-are-my-config-and-log-files) in the FAQ page for more information.
1. The input should be in a dictionary format and the key is user-defined.</br>Make sure there is a space between the colon ( : ) and open bracket ( [ ) as shown in the [Sample Configuration](#sample-configuration) then save your changes.
1. For the changes to take effect, perform any of the following:
    - Run `stop` command, `import` the config file again, and then `start`
    - Run `exit` command and restart Hummingbot

While `order_override` is in effect, it supersedes existing values of `bid_spread`, `ask_spread`, `order_amount` and `order_levels`.


## Sample Configuration

```json
order_override:
    order_1: [sell, 2.5, 5]
    order_2: [sell, 1.5, 10]
    order_3: [buy, 0.5, 1]
    order_4: [buy, 0.8, 3]
```

Using the sample input above for `order_override`, Hummingbot creates the following orders:

```
Orders:
   Level  Type  Price Spread Amount (Orig)  Amount (Adj)       Age
       2  sell 384.59  2.50%          0.1              5  00:00:01
       1  sell 380.83  1.50%          0.1             10  00:00:01
       1   buy 373.33  0.50%          0.1              1  00:00:01
       2   buy 371.45  0.80%          0.1              3  00:00:01
```

## Relevant Parameters

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **order_override** | `None` | User provided orders to directly override the orders placed by order_amount and order_level parameter.