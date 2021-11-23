---
tags:
- market making
- ⛏️ liquidity mining strategy
---

# `pure_market_making`

## 📁 [Strategy folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/strategy/pure_market_making)

## 📝 Summary

## How it works

This strategy allows Hummingbot users to run a market making strategy on a single trading pair on a `spot` exchanges. 

It places limit buy (bid) and limit sell (ask) orders on the order book at prices relative to the mid-price with spreads equal to `bid_spread` and `ask_spread`. Every `order_refresh_time` seconds, the strategy replaces existing orders with new orders with refreshed spreads and order amounts. 

In addition, the strategy contains a number of parameters to enable traders to control how orders are placed relative to their inventory position, use prices from a different order book, etc.

## 🏦 Exchanges supported

[`spot` exchanges](/exchanges/#spot)

## 👷 Maintenance

* Release added: [0.7.0](/release-notes/0.7.0/) by CoinAlpha
* Maintainer: CoinAlpha

## 🛠️ Strategy configs

[Config map](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/pure_market_making/pure_market_making_config_map.py)

| Parameter                    | Type        | Default     | Prompt New? | Prompt                                                 |
|------------------------------|-------------|-------------|-------------|--------------------------------------------------------|
| `exchange`                   | string      |             | True        | Enter your maker spot connector |
| `market`                     | string      |             | True        | Enter the token trading pair you would like to trade on [exchange] |
| `bid_spread`                 | decimal     |             | True        | How far away from the mid price do you want to place the first bid order? |
| `ask_spread`                 | decimal     |             | True        | How far away from the mid price do you want to place the first ask order? |
| `order_refresh_time`         | float       |             | True        | How often do you want to cancel and replace bids and asks (in seconds)? |
| `order_amount`               | decimal     |             | True        | What is the amount of [base_asset] per order? |
| `ping_pong_enabled`          | bool        | False       | True        | Would you like to use the ping pong feature and alternate between buy and sell orders after fills? |
| `order_levels`               | int         | 1           | False       | How many orders do you want to place on both sides? |
| `order_level_amount`         | decimal     | 0           | False       | How much do you want to increase or decrease the order size for each additional order? |
| `order_level_spread`         | decimal     | 0           | False       | Enter the price increments (as percentage) for subsequent orders? |
| `filled_order_delay`         | decimal     | 60          | False       | How long do you want to wait before placing the next order if your order gets filled (in seconds)? |
| `max_order_age`              | float       | 1800        | False       | How often do you want to cancel and replace bids and asks with the same price (in seconds)? |
| `order_refresh_tolerance_pct`| decimal     | 0           | False       | Enter the percent change in price needed to refresh orders at each cycle |
| `inventory_skew_enabled`     | bool        | False       | False       | Would you like to enable inventory skew? |
| `inventory_target_base_pct`  | decimal     | 50          | False       | What is your target base asset percentage? |
| `inventory_range_multiplier` | decimal     | 50          | False       | What is your tolerable range of inventory around the target, expressed in multiples of your total order size? |
| `hanging_orders_enabled`     | bool        | False       | False       | Do you want to enable hanging orders? |
| `hanging_orders_cancel_pct`  | decimal     | 10          | False       | At what spread percentage (from mid price) will hanging orders be canceled?|
| `order_optimization_enabled` | bool        | False       | False       | Do you want to enable best bid ask jumping? |
| `ask_order_optimization_depth`| decimal    | 0           | False       | How deep do you want to go into the order book for calculating the top ask, ignoring dust orders on the top (expressed in base asset amount)?|
| `bid_order_optimization_depth`| decimal    | 0           | False       | How deep do you want to go into the order book for calculating the top bid, ignoring dust orders on the top (expressed in base asset amount)?|
| `price_ceiling`              | decimal     | -1          | False       | Enter the price point above which only sell orders will be placed |
| `price_floor`                | decimal     | -1          | False       | Enter the price below which only buy orders will be placed |
| `price_source`               | string      | current_market| False     | Which price source to use? (current_market/external_market/custom_api) |
| `price_type`                 | string      | mid_price   | False       | Which price type to use? (mid_price/last_price/last_own_trade_price/best_bid/best_ask/inventory_cost) |
| `price_source_exchange`      | string      |             | False       | Enter external price source exchange name |
| `price_source_market`        | string      |             | False       | Enter the token trading pair on [price_source_exchange] |
| `price_source_custom_api`    | string      |             | False       | Enter pricing API URL |
| `custom_api_update_interval` | float       | 5           | False       | Enter custom API update interval in second (default: 5.0, min: 0.5) |
| `inventory_price`            | decimal     | 1           | False       | What is the price of your base asset inventory? |
| `add_transaction_costs`      | bool        | False       | False       | Do you want to add transaction costs automatically to order prices? |
| `minimum_spread`             | decimal     | -100        | False       | At what minimum spread should the bot automatically cancel orders? |
| `take_if_crossed`            | bool        | False       | False       | Do you want to take the best order if orders cross the orderbook? |
| `order_override`             | bool        | None        | False       |  |

## 📓 Description

[Trading logic](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/pure_market_making/pure_market_making.pyx)

!!! note "Approximation only"
    The description below is a general approximation of this strategy. Please inspect the strategy code in **Trading Logic** above to understand exactly how it works.

### Architecture

The built-in pure market making strategy in Hummingbot periodically requests limit order proposals from configurable order pricing and sizing plugins, and also periodically refreshes the orders by cancelling existing limit orders.

Here's a high level view of the logic flow inside the built-in pure market making strategy.

![Figure 5: Pure market making strategy logical flowchart](/assets/img/pure-mm-flowchart.svg)

The pure market making strategy operates in a tick-by-tick manner. Each tick is typically 1 second, although it can be programmatically modified to longer or shorter durations.

At each tick, the pure market making strategy would first query the order filter plugin whether to proceed or not. Assuming the answer is yes, then it'll query the order pricing and sizing plugins and calculate whether and what market making orders it should emit. At the same time, it'll also look at any existing limit orders it previously placed on the market and decide whether it should cancel those.

The process repeats over and over at each tick, causing limit orders to be periodically placed and cancelled according to the proposals made by the order pricing and sizing plugins.

### Refreshing Orders

For each limit order that was emitted by the pure market making strategy, an expiry timestamp would be generated for that order and the order will be tracked by the strategy. The time until expiry for new orders is configured via the `order_refresh_time` parameter. 

After an order's expiration time is reached, the pure market making strategy will create a cancel order proposal for that order.

### Executing Order Proposals

After collecting all the order pricing, sizing and cancel order proposals from plugins and the internal refresh order logic - the pure market making strategy logic will merge all of the proposals and execute them.

### Example Order Flow

Below is a hypothetical example of how the pure market making strategy works for a few clock ticks.

* At clock tick `t`, there may be existing limit orders on both the bid and ask sides, and both have not yet expired. The proposed sizes for new orders will be 0, and there will be no cancel order proposals. So the strategy will do nothing for this clock tick.
* At clock tick `t+1`, the limit bid order has expired. The strategy will then generate a cancel order proposal for the expired bid order. The cancellation will then be send to the exchange and executed.
* At clock tick `t+2`, the strategy loops through its trading logic and notices there's no longer an order at the bid side. So it'll propose a non-zero order size for a new bid order. Let's assume the existing ask order hasn't expired yet, so no cancellation proposals will be generated at this clock tick. At the execution phase, the strategy will simply create a bid order calculated from the current market mid-price. Thus the bid order is refreshed.

This cycle of order creation and order cancellation will repeat again and again for as long as the strategy is running. If a limit order is completely filled by a market order, the strategy will simply refresh it at the next clock tick.

<!-- ## Schematic

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

See [Strategy Configs](/strategy-configs/) for more information about the advanced parameters and how to use them.

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

Whether to alternate between buys and sells, for more information on this parameter, click this [link](/strategy-configs/ping-pong/).

** Prompt: **

```json
Would you like to use the ping pong feature and alternate between buy and sell orders after fills?
>>>
```

!!! tip
    For autocomplete inputs during configuration, when going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.

## **Configure parameters on the fly**

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
    Reconfiguring of `inventory_target_base_pct` for DEX connectors is not working at the moment. -->
