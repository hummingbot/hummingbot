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

When using the [multiple order mode](#multiple-order-configuration), this may result in some (or none) of the orders being placed on one side.

**Example:**

`bid order amount 1 * bid price 1` < `exchange's minimum order size`<br/>
`bid order amount 2 * bid price 2` > `exchange's minimum order size`

Only the 2nd buy order will be created.

## Basic and Advanced Modes

We aim to teach new users the basics of market making, while enabling experienced users to exercise more control over how their bots behave. By default, when you run `config`, we ask you to enter the basic parameters needed for a market making bot.

Afterwards, you should see the following question:

```
Would you like to proceed with advanced configuration? (Yes/No) >>>
```

Responding `Yes` to this question will walk you through in setting up the advanced parameters for this strategy. Responding `No` will leave the advanced parameters to their default values.

See [Advanced Market Making](/strategies/advanced-mm) for more information about these parameters and how to use them.


## Basic Configuration Walkthrough

!!! tip "Tip: Autocomplete inputs during configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.

| Prompt | Description |
|-----|-----|
| `What is your market making strategy >>>` | Enter `pure_market_making`. |
| `Import previous configs or create a new config file? (import/create) >>>` | Enter `create` to create a new config file.<br/><br/>Enter `import` to specify the existing config file name you want to use. |
| `Enter your maker exchange name >>>` | The exchange where the bot will place bid and ask orders.<br/><br/>Currently available options: `binance`, `radar_relay`, `coinbase_pro`, `bamboo_relay`, `huobi`, `bittrex`, `dolomite`, `liquid`, `kucoin` *(case sensitive)* |
| `Enter the token symbol you would like to trade on [exchange name] >>>` | Enter the token symbol for the *maker exchange*.<br/>Example input: `ETH-USD`<br/> |
| `How far away from the mid price do you want to place the first bid order? (Enter 0.01 to indicate 1%) >>>` | This sets `bid_place_threshold` ([see below](#configuration-parameters)). |
| `How far away from the mid price do you want to place the first ask order? (Enter 0.01 to indicate 1%) >>>` | This sets `ask_place_threshold` ([see below](#configuration-parameters)). |
| `How often do you want to cancel and replace bids and asks (in seconds)? >>>` | This sets the `cancel_order_wait_time` ([see below](#configuration-parameters)). |
| `What is the amount of [base_asset] per order? (minimum [min_amount]) >>> ` | This sets `order_amount` ([see below](#configuration-parameters)). |


## Basic Configuration Parameters

The following parameters are fields in Hummingbot configuration files located in the `/conf` folder (e.g. `conf/conf_pure_market_making_strategy_[#].yml`).

| Term | Definition |
|------|------------|
| **bid\_place\_threshold** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%). The strategy will place the buy (bid) order 1% away from the mid price if set to 0.01. <br/><br/>*Example: Assuming the following, Top bid : 99, Top ask: 101 ; mid price: 100 ( (99+ 101)/2 ). If you set bid_place_threshold to 0.1 which is 10%, it will place your buy order (bid) at 10% below mid price of 100 which is 90.*
| **ask\_place\_threshold** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%). The strategy will place the sell (ask) order 1% away from the mid price if set to 0.01. <br/><br/>*Example: Assuming the following, Top bid : 99, Top ask: 101 ; mid price: 100 ( (99+ 101)/2 ). If you set ask_place_threshold to 0.1 which is 10%, it will place your sell order (ask) at 10% above mid price of 100 which is 110.*
| **order\_amount** | The order amount for the limit bid and ask orders. <br/> Ensure you have enough quote and base tokens to place the bid and ask orders. The strategy will not place orders if you do not have sufficient balance for both sides of the order. <br/>
| **cancel\_order\_wait\_time** | An amount in seconds, which is the duration for the placed limit orders. _Default value: 30 seconds_. <br/><br/> The limit bid and ask orders are cancelled and new bids and asks are placed according to the current mid price and settings at this interval.
