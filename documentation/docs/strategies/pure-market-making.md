# Pure Market Making

## How it Works

In the pure market making strategy, Hummingbot continually posts limit bid and ask offers on a market and waits for other market participants ("takers") to fill their orders.

Users can specify how far away ("spreads") from the mid price the bid and asks are, the order quantity, and how often prices should be updated (order cancels + new orders posted).

!!! warning
    Please exercise caution while running this strategy and set appropriate [kill switch](/advanced/kill-switch/) rate. The current version of this strategy is intended to be a basic template that users can test and customize. Running the strategy with substantial capital without additional modifications may result in losses.

### Schematic

The diagram below illustrates how market making works. Hummingbot makes a market by placing buy and sell orders on a single exchange, specifying prices and sizes.

<small><center>***Figure 1: Hummingbot makes a market on an exchange***</center></small>

![Figure 1: Hummingbot makes a market on an exchange](/assets/img/pure-mm.png)

## Prerequisites

### Inventory

1. You will need to hold sufficient inventory of quote and/or base currencies on the exchange to place orders of the exchange's minimum order size.
2. You will also need some ETH to pay gas for transactions on a decentralized exchange (if applicable).

### Minimum Order Size

When placing orders, if the size of the order determined by the order price and quantity is below the exchange's minimum order size, then the orders will not be created.

**Example:**

`bid order amount * bid price` < `exchange's minimum order size`<br/>
`ask order amount * ask price` > `exchange's minimum order size`

Only a sell order will be created but no buy order.


## Basic and Advanced Configuration

We aim to teach new users the basics of market making, while enabling experienced users to exercise more control over how their bots behave. By default, when you run `create` we ask you to enter the basic parameters needed for a market making bot.

See [Advanced Market Making](/strategies/advanced-mm) for more information about the advanced parameters and how to use them.


## Basic Configuration Parameters and Walkthrough

The following parameters are fields in Hummingbot configuration files located in the `/conf` folder (e.g. `conf_pure_mm_[#].yml`).

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **exchange** | `Enter your maker exchange name` | The exchange where the bot will place bid and ask orders. |
| **market** | `Enter the token trading pair you would like to trade on [exchange]` | Token trading pair symbol you would like to trade on the exchange. |
| **bid_spread** | `How far away from the mid price do you want to place the first bid order?` | The strategy will place the buy (bid) order on a certain % away from the mid price. |
| **ask_spread** | `How far away from the mid price do you want to place the first ask order?` | The strategy will place the sell (ask) order on a certain % away from the mid price. |
| **minimum_spread**| `At what distance/spread from the mid price do you want the orders to be cancelled?` | The strategy will check every tick and cancel the active orders if an order's spread is less than the minimum spread parameter. |
| **order_refresh_time** | `How often do you want to cancel and replace bids and asks (in seconds)?` | An amount in seconds, which is the duration for the placed limit orders. <br/><br/> The limit bid and ask orders are cancelled and new orders are placed according to the current mid price and spreads at this interval. |
| **order_amount** | `What is the amount of [base_asset] per order? (minimum [min_amount])` | The order amount for the limit bid and ask orders. <br/><br/> Ensure you have enough quote and base tokens to place the bid and ask orders. The strategy will not place any orders if you do not have sufficient balance on either sides of the order. <br/>
| **inventory_skew_enabled** | `On [exchange], you have [amount of base assets] and [amount of quote assets]. By market value, your current inventory split is [base asset ratio] and [quote asset ratio]. Would you like to keep this ratio? (Yes/No)` | Allows the user to set and maintain a target inventory split between base and quote assets. <br/><br/> Enter `Yes` to keep your current inventory ratio. Enter `No` to specify the inventory ratio target. <br/><br/> This is an advanced parameter we added during basic configuration walkthrough. See [Inventory Skew](https://docs.hummingbot.io/strategies/advanced-mm/inventory-skew/) for more information on this feature.
| **inventory_target_base_pct** | `What is your target base asset percentage? Enter 50 for 50%` | Target amount held of the base asset, expressed as a percentage of the total base and quote asset value. <br/><br/> This question prompts when answering `No` to the above question.
| **order_expiration_time** | `How long should your limit orders remain valid until they expire and are replaced?` | Sets the expiration of limit orders on 0x relayers like Radar Relay and Bamboo Relay since cancellation is an on-chain event requiring gas (you become your own counter party to void the contract), while expiration is not an on chain event as the order is invalidated by the timestamp. <br/><br/> If trading on a centralized exchange, **order refresh time** will be used.

!!! tip "Tip: Autocomplete inputs during configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.