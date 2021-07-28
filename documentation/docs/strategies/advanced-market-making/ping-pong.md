# Ping Pong

**Updated as of `v0.28.0`**

This feature enables the ping pong strategy, in which Hummingbot alternates buy and sell orders.


## How It Works

By default, this parameter is set to `False`. When enabled, after a filled order event on either side (buy/sell) it will only create orders on the opposite side on the next refresh.

For example, if your buy order is filled and the sell order was cancelled the bot will keep creating sell orders only until it gets filled.

Stopping the strategy using the `stop` command breaks the current ping pong logic. Upon restarting the bot will initially create both buy and sell orders again assuming you have enough balance to place orders on each side.


## Ping pong with single order level

The scenario below shows how ping pong balances trades when one side is filled.

1. Buy order $b1$ and sell order $s1$ are created</br>
1. $b1$ gets filled and $s1$ is cancelled when not filled</br>
1. Sell order $s2$ is created</br>
1. $s2$ gets filled</br>
1. Buy order $b3$ and sell order $s3$ are created</br>

Notice that the buy order $b2$ was not created in an attempt to offset the previous trade.


## Ping pong with multiple order levels

Let's say initially we have 2 orders on each side, buy orders $b1$, $b2$, and sell orders $s1$, $s2$.

1. $b1$ gets filled and $b2$, $s1$, $s2$ are cancelled when not filled
1. Buy order $b3$ and sell orders $s3$, $s4$ are created
1. $s3$ gets filled and $b3$, $s4$ are cancelled when not filled
1. Buy order $b4$ and sell order $s5$ are created
1. $s5$ gets filled and $b4$ is cancelled when not filled
1. Buy order $b5$ is created
1. $b5$ gets filled
1. Buy orders $b6$, $b7$ and sell orders $s6$, $s7$ are created


## Relevant Parameters

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **ping_pong_enabled** | `Would you like to use the ping pong feature and alternate between buy and sell orders after fills?` | Whether to alternate between buys and sells. |