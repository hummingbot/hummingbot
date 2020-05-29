# Hanging Orders

**Updated as of `v0.28.0`**

This feature keeps orders "hanging" (or not cancelled and remaining on the order book) if a matching order has been filled on the other side of the order book (bid vs. ask order books).

## How It Works

Typically, orders are placed as pairs in single order mode (1 buy and 1 sell order), and when a buy or sell order is filled, the other order is cancelled. The parameter `hanging_orders_enabled` allows Hummingbot to leave the order on the other side hanging (not cancelled) whenever one side is filled.

The hanging order will be cancelled in the following conditions:

1. The spread goes above the specified `hanging_orders_cancel_pct` value
2. Sending `stop` or `exit` command

Type `config hanging_orders_enabled` and `config hanging_orders_cancel_pct` to set values for these parameters. 

## Illustrative Example
Suppose you are market making for the `ETH-USD` pair with a mid-market price of 200 USD ($t_0$). You set your bid spread and ask spread to 1%. Thus, the bid price is 198 USD and the ask price is 202 USD. Now suppose that a market taker (someone taking a position in the market) thinks the price of Ethereum will rise, so they fill your ask order 202 ($t_1$). If `hanging_orders_enabled` is set to False, the bid-order you just placed at 198 would be cancelled. If `hanging_orders_enabled` is set to True, the bid order stays on the order book. Suppose now that the mid-market price rises to 201 ($t_2$). The hanging bid order, priced at 198, is about a 1.5% spread. If another market taker thinks that the market will decrease substantially as a reaction, then they may fill your bid order ($t_3$). At this point, if you sell at market, you can profit an additional $3 having set `hanging_orders_enabled` is set to True.

![Sample Market](/assets/img/hanging_orders_example_market.png)

Note that if an open hanging order spread exceeds the `hanging_orders_cancel_pct` parameter, the hanging order will be canceled.


## Sample Configurations

Let's see how this configuration works in the scenario below:

```json
- filled_order_delay: 60.0
- hanging_orders_enabled: True
- hanging_orders_cancel_pct: 2
```

![](/assets/img/hanging_order1.png)

When the buy order `...1497` was completely filled, it will not cancel the sell order `...1840`. After 60 seconds, Hummingbot will create a new set of buy and sell orders. The `status` output will show all active orders while indicating which orders are hanging.

![](/assets/img/hanging_order2.png)

The hanging order will stay outstanding and will be cancelled if its spread goes above 2% as specified in our `hanging_orders_cancel_pct`.

![](/assets/img/hanging_order3.png)


## Relevant Parameters

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **hanging_orders_enabled** | `Do you want to enable hanging orders? (Yes/No)` | When enabled, the orders on the side opposite to the filled orders remains active. |
| **hanging_orders_cancel_pct** | `At what spread percentage (from mid price) will hanging orders be canceled?` | Cancels the hanging orders when their spread goes above this value. |