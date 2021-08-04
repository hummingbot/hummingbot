---
title: "Pure Market Making"
description: Info on developing pure market making
---

## Architecture

The built-in pure market-making strategy in Hummingbot periodically requests limit order proposals from configurable order pricing and sizing plugins. It periodically refreshes the orders by canceling existing limit orders.

Here's a high-level view of the logic flow inside the built-in pure market-making strategy.

![Figure 5: Pure market making strategy logical flowchart](/img/pure-mm-flowchart.svg)

The pure market-making strategy operates in a tick-by-tick manner, as described in the [Strategies Overview](/strategies/overview) document. Each tick is typically 1 second, although it can be programmatically modified to longer or shorter durations.

The pure market-making strategy would first query the order filter plugin at each tick to proceed. Assuming the answer is yes, then it'll query the order pricing and sizing plugins and calculate whether and what market-making orders it should emit. At the same time, it'll also look at any existing limit orders it previously placed on the market and decide whether it should cancel those.

The process repeats over and over at each tick, causing limit orders to be periodically placed and canceled according to the proposals made by the order pricing and sizing plugins.

## Plugins

There are a few plugin interfaces that the pure market-making strategy depends on arriving at its order proposals.

![Figure 6: Pure market making strategy plugins](/img/pure-mm-uml.svg)

- OrderFilterDelegate

  Makes the Yes / No decision to proceed with processing the current clock tick or not.

- OrderPricingDelegate

  Returns a PriceProposal with lists of prices for creating bid and ask orders. If no order should be created at the current clock tick (e.g. because there're already existing orders), it may choose to return empty lists instead.

- OrderSizingDelegate

  Returns a SizingProposal with lists of order sizes for creating bid and ask orders, given the pricing proposal. If a proposed order at a certain price should not be created (e.g. there's not enough balance on the exchange), it may choose to return zero sizes for that order instead.

## Built-in Plugins

If you configure the pure market-making strategy with the `order_levels` parameter set to 1, then Hummingbot will use ConstantSpreadPricingDelegate and ConstantSizeSizingDelegate for the pricing and sizing plugins.

Alternatively, setting `order_levels` greater than 1 places multiple levels of orders on each side of the order book. In this case, Hummingbot will use ConstantMultipleSpreadPricingDelegate and StaggeredMultipleSizeSizingDelegate for the pricing and sizing plugins instead.

### ConstantSpreadPricingDelegate

The logic of ConstantSpreadPricingDelegate is simple. It will always propose a bid and an ask order at a pre-configured spread from the current mid-price.

```cython
object bid_price = mid_price * (Decimal(1) - self.bid_spread)
object ask_price = mid_price * (Decimal(1) + self.ask_spread)
```

It doesn't check whether you have existing orders or have enough balance to create the orders; this is normal because the sizing delegate is responsible for that.

### ConstantSizeSizingDelegate

The logic inside ConstantSizeSizingDelegate is more involved because it checks whether there are existing limit orders that are still active and whether there's enough balance in the exchange to create new orders.

In addition, this delegate is responsible for "quantizing" the orders, which means conforming them to the tick size and minimum order size required by this particular exchange's trading rules. Note that if the proposed order size is smaller than the minimum order size, the order size will be reduced to 0.

If all the checks are green (i.e., no active limit orders, and enough balance to make new orders) and after it has quantized the orders, the delegate will make constant order size proposals with the pre-configured size on both the bid and ask sides. Otherwise, it'll propose 0 order sizes.

## Refreshing Orders

For each limit order that was emitted by the pure market-making strategy, an expiry timestamp would be generated for that order, and the strategy will track the order. The time until expiry for new orders is configured via the **order_refresh_time** parameter (See [parameters](/strategies/pure-market-making/#basic-configuration-parameters-and-walkthrough) in main documentation).

After an order's expiration time is reached, the pure market-making strategy will create a cancel order proposal for that order.

## Executing Order Proposals

After collecting all the order pricing, sizing, and cancel order proposals from plugins and the internal refresh order logic - the pure market-making strategy logic will merge all of the proposals and execute them.

## Example Order Flow

Below is a hypothetical example of how the pure market-making strategy works for a few clock ticks.

At clock tick _n_, there may be existing limit orders on both the bid and ask sides, and both have not yet expired. Assuming we're using the `ConstantSizeSizingDelegate` and `ConstantSpreadPricingDelegate` in this case, the proposed sizes for new orders will be 0. There'll be no cancel order proposals. So the strategy will do nothing for this clock tick.

At clock tick _n+1_, the limit bid order has expired. The strategy will then generate a cancel order proposal for the expired bid order. The cancellation will then be sent to the exchange and executed.

At clock tick _n+2_, the `ConstantSizeSizingDelegate` notices there's no longer order at the bid side. So it'll propose a non-zero order size for a new bid order. Let's assume the existing ask order hasn't expired yet, so no cancellation proposals will be generated at this clock tick. Instead, the strategy will create a bid order from the current market mid-price at the execution phase. Thus the bid order is refreshed.

This cycle of order creation and order cancellation will repeat again and again for as long as the strategy is running. For example, if a market order fills a limit order, the strategy will refresh it at the next clock tick.
