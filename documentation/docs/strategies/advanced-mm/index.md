# Advanced Market Making

These advanced parameters give you more control over how your bot behaves. Please take the time to understand how these parameters work before risking extensive capital with bots that utilize them.

## How to Configure Advanced Parameters

There are a few ways to configure these parameters:

1. Run `config` to go through the normal strategy configuration process and answer `Yes` to the final question `Would you like to proceed with advanced configuration?`
2. Run `list configs` to see the current strategy. Run command `config advanced_mode`. This will walk you through in reconfiguring all the advanced parameters.
3. Outside of the Hummingbot client, you can edit the strategy configuration file directly and then import it later.

## Multiple Orders

This feature allows you to set multiple levels of orders on each side and gives you more fine-grained control over the spreads and sizes of each set of orders. 

See [Multiple Orders](./multiple-orders) for more information.

## Inventory Skew

This feature lets you set and maintain a target inventory split between the base and quote assets. It prevents your overall inventory level from changing too much and may result in more stable performance in volatile markets.

See [Inventory Skew](./inventory-skew) for more information.

## Hanging Orders

This feature prevents keeps orders "hanging" (or not cancelled and remaining on the order book) if a matching order has been filled on the other side of the order book.

See [Hanging Orders](./hanging-orders) for more information.

## Filled Order Delay

By default, Hummingbot places orders as soon as there are no active orders; i.e., Hummingbot immediately places a new order to replace a filled order. If there is a sustained movement in the market in any one direction for some time, there is a risk of continued trading in that direction: For example, continuing to buy and accumulate base tokens in the case of a prolonged downward move or continuing to sell in the case of a prolonged upward move.

The `filled_order_replenish_wait_time` parameter allows for a delay when placing a new order in the event of an order being filled, which will help mitigate the above scenarios.

>**Example**: If you have a buy order that is filled at 1:00:00 and the delay is set to `60` seconds, the next orders placed will be at 1:01:00. The sell order is also cancelled within this delay period and placed at 1:01:00 to ensure that both buy and sell orders stay in sync.

**Relevant Parameters**

| Parameter | Prompt | Definition | Default Value |
|-----------|--------|------------|---------------|
| **filled_order_replenish_wait_time** | `How long do you want to wait before placing the next order if your order gets filled (in seconds)? >>>` | How long to wait before placing the next order in case your order gets filled. | `60.0` |


## Adding Transaction Costs to Prices

Transaction costs can now be added to the price calculation. `fee_pct` refers to the percentage maker fees per order (generally common in Centralized exchanges) while `fixed_fees` refers to the flat fees (generally common in Decentralized exchanges).

- The bid order price will be calculated as:

![Bid price with transaction cost](/assets/img/trans_cost_bid.PNG)

- The ask order price will be calculated as:

![Ask price with transaction cost](/assets/img/trans_cost_ask.PNG)

Adding the transaction cost will reduce the bid order price and increase the ask order price i.e. putting your orders further away from the mid price.

We currently display warnings if the adjusted price post adding the transaction costs is 10% away from the original price. If the buy price with the transaction cost is zero or negative, it is not profitable to place orders and orders will not be placed.

**Relevant Parameters**

| Parameter | Prompt | Definition | Default Value |
|-----------|--------|------------|---------------|
| **add_transaction_costs** | `Do you want to add transaction costs automatically to order prices? (Yes/No) >>>` | Whether to enable adding transaction costs to order price calculation. | `false` |