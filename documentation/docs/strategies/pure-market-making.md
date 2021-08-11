# Pure Market Making

## How it works

In the pure market making strategy, Hummingbot continually posts the limit bid and ask offers on the market, and waits for other market participants ("takers") to fill their orders.

Users can specify how far away ("spreads") from the mid-price the bid and asks are, the order quantity, and how often prices should be updated (order cancels + new orders posted).

!!! warning
    Please exercise caution while running this strategy and set appropriate [kill switch](/features/kill-switch/) rate. The current version of this strategy is intended to be a basic template that users can test and customize. Running the strategy with substantial capital without additional modifications may result in losses.

## Schematic

The diagram below illustrates how market making works. Hummingbot makes a market by placing buy and sell orders on a single exchange, specifying prices and sizes.

<small>
  <center>**_Figure 1: Hummingbot makes a market on an exchange_**</center>
</small>

![Figure 1: Hummingbot makes a market on an exchange](/assets/img/pure-mm.png)

## Prerequisites

### Inventory

- You will need to hold a sufficient inventory of quote and/or base currencies on the exchange to place orders of the exchange's minimum order size.
- You will also need some ETH to pay gas for transactions on a decentralized exchange (if applicable).

### Minimum order size

When placing orders, if the size of the order determined by the order price and quantity is below the exchange's minimum order size, then the orders will not be created.

**Example:**

`bid order amount * bid price` < `exchange's minimum order size`<br/>
`ask order amount * ask price` > `exchange's minimum order size`

Only a sell order will be created, but no buy order.

## Basic parameters

We aim to teach new users the basics of market-making while enabling experienced users to exercise more control over how their bots behave. By default, when you run `create`, we ask you to enter the basic parameters needed for a market-making bot.

See [Advanced Market Making](/strategies/adv-market-making) for more information about the advanced parameters and how to use them.

The following parameters are fields in Hummingbot configuration files located in the `/conf` folder (e.g. `conf_pure_mm_[#].yml`).

### `exchange`

The exchange where the bot will place bid and ask orders.

** Prompt: **

```json
Enter your maker spot connector
>>> binance
```

### `market`

Token trading pair symbol you would like to trade on the exchange.

** Prompt: **

```json
Enter the token trading pair you would like to trade on the exchange
>>> BTC-USDT
```

### `bid_spread`

The strategy will place the buy (bid) order on a certain % away from the mid-price.

** Prompt: **

```json
How far away from the mid price do you want to place the first bid order?
>>> 2
```

### `ask_spread`

The strategy will place the sell (ask) order on a certain % away from the mid-price.

** Prompt: **

```json
How far away from the mid price do you want to place the first ask order?
>>> 3
```

### `order_refresh_time`

An amount in seconds, which is the duration for the placed limit orders. The limit bid and ask orders are canceled, and new orders are placed according to the current mid-price and spread at this interval.

** Prompt: **

```json
How often do you want to cancel and replace bids and asks (in seconds)?
>>> 10
```

### `order_amount`

The order amount for the limit bid and ask orders. Ensure you have enough quote and base tokens to place the bid and ask orders. The strategy will not place any orders if you do not have sufficient balance on either side of the order. <br/>

** Prompt: **

```json
What is the amount of [base_asset] per order? (minimum [min_amount])
>>>
```

### `ping_pong_enabled`

Whether to alternate between buys and sells, for more information on this parameter, click this [link](https://docs.hummingbot.io/strategies/ping-pong/).

** Prompt: **

```json
Would you like to use the ping pong feature and alternate between buy and sell orders after fills?
>>>
```

!!! tip
    For autocomplete inputs during configuration, when going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.

## ** Configure parameters on the fly **

Currently, only the following parameters can be reconfigured without stopping the bot. The changes will take effect in the next order refresh.

- bid_spread
- ask_spread
- order_amount
- order_levels
- order_level_spread
- inventory_target_base_pct
- inventory_range_multiplier
- filled_order_delay

!!! note
    Reconfiguring of `inventory_target_base_pct` for DEX connectors is not working at the moment.
