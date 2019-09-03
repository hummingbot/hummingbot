# Pure Market Making

## Architecture

The built-in pure market making strategy in Hummingbot periodically requests limit order proposals from configurable order pricing and sizing plugins, and also periodically refreshes the orders by cancelling existing limit orders.

Here's a high level view of the logic flow inside the built-in pure market making strategy.

![Figure 5: Pure market making strategy logical flowchart](/assets/img/pure-mm-flowchart.svg)

The pure market making strategy operates in a tick-by-tick manner, as described in the [Strategies Overview](/strategies) document. Each tick is typically 1 second, although it can be programmatically modified to longer or shorter durations.

At each tick, the pure market making strategy would first query the order filter plugin whether to proceed or not. Assuming the answer is yes, then it'll query the order pricing and sizing plugins and calculate whether and what market making orders it should emit. At the same time, it'll also look at any existing limit orders it previously placed on the market and decide whether it should cancel those.

The process repeats over and over at each tick, causing limit orders to be periodically placed and cancelled according to the proposals made by the order pricing and sizing plugins.

## Plugins

There are a few plugin interfaces that the pure market making strategy depends on arriving at its order proposals.

![Figure 6: Pure market making strategy plugins](/assets/img/pure-mm-uml.svg)

* [`OrderFilterDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/order_filter_delegate.pxd)

    Makes the Yes / No decision to proceed with processing the current clock tick or not.

* [`OrderPricingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/order_pricing_delegate.pxd)

    Returns a [`PriceProposal`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/data_types.py) with lists of prices for creating bid and ask orders. If no order should be created at the current clock tick (e.g. because there're already existing orders), it may choose to return empty lists instead.

* [`OrderSizingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/order_sizing_delegate.pxd)

    Returns a [`SizingProposal`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/data_types.py) with lists of order sizes for creating bid and ask orders, given the pricing proposal. If a proposed order at a certain price should not be created (e.g. there's not enough balance on the exchange), it may choose to return zero size for that order instead.

## Built-in Plugins

If you configure the pure market making strategy with multiple orders **disabled**, then Hummingbot will be using [`ConstantSpreadPricingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/constant_spread_pricing_delegate.pyx) and [`ConstantSizeSizingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/constant_size_sizing_delegate.pyx) for the pricing and sizing plugins.

### ConstantSpreadPricingDelegate

If you look into the logic of the [`ConstantSpreadPricingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/constant_spread_pricing_delegate.pyx), it's extremely simple - it'll always propose a bid and an ask order at a pre-configured spread from the current mid-price. It doesn't do any checks about whether you have existing orders, or have enough balance to create the orders - but that's fine.

### ConstantSizeSizingDelegate

The logic inside [`ConstantSizeSizingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/constant_size_sizing_delegate.pyx) looks a bit more involved, because it's checking whether there're existing limit orders that are still active, and also whether there's enough balance in the exchange to create new orders. But beyond the checks, it's really just proposing constant order size proposals.

If all the checks are green (i.e. no active limit orders, and enough balance to make new orders), then it will make an order size proposal with the pre-configured size on both the bid and ask sides. Otherwise, it'll propose 0 order sizes.

If you configure the pure market making strategy with multiple orders **enabled**, then Hummingbot will be using [`ConstantMultipleSpreadPricingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/constant_multiple_spread_pricing_delegate.pyx) and [`StaggeredMultipleSizeSizingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/staggered_multiple_size_sizing_delegate.pyx) for the pricing and sizing plugins instead.

## Refreshing Orders

For each limit order that was emitted by the pure market making strategy, an expiry timestamp would be generated for that order and the order will be tracked by the strategy. The time until expiry for new orders is configured via the **cancel_order_wait_time** option in [Configuration Parameters](#configuration-parameters).

Once an order's expiration time has passed, the pure market making strategy will create a cancel order proposal for that order.

## Executing Order Proposals

After collecting all the order pricing, sizing and cancel order proposals from plugins and the internal refresh order logic - the pure market making strategy logic will merge all of the proposals and execute them.

## Example Order Flow

Below is a hypothetical example of how the pure market making strategy works for a few clock ticks.

At clock tick *n*, there may be existing limit orders on both the bid and ask sides, and both have not yet expired. Assuming we're using the `ConstantSizeSizingDelegate` and `ConstantSpreadPricingDelegate` in this case, the proposed sizes for new orders will be 0. There'll be no cancel order proposals. So the strategy will do nothing for this clock tick.

At clock tick *n+1*, the limit bid order has expired. The strategy will then generate a cancel order proposal for the expired bid order. The cancellation will then be send to the exchange and executed.

At clock tick *n+2*, the `ConstantSizeSizingDelegate` notices there's no longer an order at the bid side. So it'll propose a non-zero order size for a new bid order. Let's assume the existing ask order hasn't expired yet, so no cancellation proposals will be generated at this clock tick. At the execution phase, the strategy will simply create a bid order calculated from the current market mid-price. Thus the bid order is refreshed.

This cycle of order creation and order cancellation will repeat again and again for as long as the strategy is running. If a limit order is completely filled by a market order, the strategy will simply refresh it at the next clock tick.
