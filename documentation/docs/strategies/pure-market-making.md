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


## Basic Configuration Walkthrough

These are the questions prompted during configuration of the strategy. The parameters are explained in the section further down below.

| Prompt | Parameter |
|--------|-----------|
| `What is your market making strategy >>>` <img width=400/> | `strategy` <img width=600/> |
| `Enter your maker exchange name >>>` | `exchange` |
| `Enter the token trading pair you would like to trade on [exchange] (e.g. ZRX-ETH) >>>` | `market` |
| `How far away from the mid price do you want to place the first bid order? (Enter 1 to indicate 1%) >>>` | `bid_spread` |
| `How far away from the mid price do you want to place the first ask order? (Enter 1 to indicate 1%) >>>` | `ask_spread` |
| `How often do you want to cancel and replace bids and asks (in seconds)? >>>` | `order_refresh_time` |
| `What is the amount of [base_asset] per order? (minimum [min_amount]) >>> ` | `order_amount` |
| `On [exchange], you have [amount of base assets] and [amount of quote assets]. By market value, your current inventory split is [base asset ratio] and [quote asset ratio]. Would you like to keep this ratio? (Yes/No) >>>` | `inventory_skew_enabled` |
| `What is your target base asset percentage? Enter 50 for 50% >>>` | `inventory_target_base_pct` |

!!! tip "Tip: Autocomplete inputs during configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.


## Basic Configuration Parameters

The following parameters are fields in Hummingbot configuration files located in the `/conf` folder (e.g. `conf_pure_mm_[#].yml`).

| Term | Definition |
|------|------------|
| **exchange** | The exchange where the bot will place bid and ask orders.<br/><br/>Currently available options: `binance`, `radar_relay`, `coinbase_pro`, `bamboo_relay`, `huobi`, `bittrex`, `dolomite`, `liquid`, `kucoin` (case sensitive)
| **market** | Token trading pair symbol you would like to trade on the exchange.
| **bid\_spread** | The strategy will place the buy (bid) order on a certain % away from the mid price.
| **ask\_spread** | The strategy will place the sell (ask) order on a certain % away from the mid price.
| **order\_refresh\_time** | An amount in seconds, which is the duration for the placed limit orders. <br/><br/> The limit bid and ask orders are cancelled and new orders are placed according to the current mid price and spreads at this interval.
| **order\_amount** | The order amount for the limit bid and ask orders. <br/><br/> Ensure you have enough quote and base tokens to place the bid and ask orders. The strategy will not place any orders if you do not have sufficient balance on either sides of the order. <br/>
| **inventory\_skew\_enabled** | Allows the user to set and maintain a target inventory split between base and quote assets. <br/><br/> This is an advanced parameter we added during basic configuration walkthrough. See [Inventory Skew](/advanced-mm/inventory-skew) for more information.
| **inventory\_target\_base\_pct** |  Target amount held of the base asset, expressed as a percentage of the total base and quote asset value. This question prompts when answering `No` to the question for `inventory_skew_enabled`.