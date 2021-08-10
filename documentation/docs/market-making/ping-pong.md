# Ping Pong

**Updated as of `v0.28.0`**

This feature enables the ping pong strategy, in which Hummingbot alternates buy and sell orders.

## `ping_pong_enabled`

Whether to alternate between buys and sells.

** Prompt: **

```json
Would you like to use the ping pong feature and alternate between buy and sell orders after fills?
>>>
```

## How it works

The ping pong strategy tries to keep buys and sells balanced by only creating orders on the opposite side of an order that is filled. It will keep on creating orders on the opposite side of the filled order as long as `ping_pong` is set to enabled. For example:

![](/assets/img/ping-pong-mode.png)

Because the buy order from period 1 was filled, the bot stops placing buy orders, and only places sell orders (periods 2-4). Only when a sell order is eventually filled (period 4) that's the time that it will resume creating both buy and sell orders (period 5).

By default, this parameter is set to `False`. When enabled, after a filled order event on either side (buy/sell) it will only create orders on the opposite side on the next refresh.

For example, if your buy order is filled and the sell order was canceled the bot will keep creating sell orders only until it gets filled.

Stopping the strategy using the `stop` command breaks the current ping pong logic. Upon restarting, the bot will initially create both buy and sell orders, assuming you have enough balance to place orders on each side.

## Ping pong with single order level

The scenario below shows how ping pong balances trades when one side is filled.

1. Buy order b1 and sell order s1 are created
2. b1 gets filled, and s1 is canceled when not filled
3. Sell order s2 is created
4. s2 gets filled
5. Buy order b3 and sell order s3 are created

Notice that the buy order b2 was not created in an attempt to offset the previous trade.

## Ping pong with multiple order levels

Let's say initially we have 2 orders on each side, buy orders b1, b2, and sell orders s1, s2.

1. b1 gets filled, and b2, s1, s2 are canceled when not filled
2. Buy order b3 and sell orders s3, s4 are created
3. s3 gets filled, and b3, s4 are canceled when not filled
4. Buy order b4 and sell order s5 are created
5. s5 gets filled, and b4 is canceled when not filled
6. Buy order b5 is created
7. b5 gets filled
8. Buy orders b6, b7, and sell orders s6, s7 are created
