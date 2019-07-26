## Strategies Architecture

![StrategyBase class relations](/assets/img/strategy-uml.svg)

Strategy modules in Hummingbot are modules that monitor markets and make trading decisions. All strategy classes are derived from the [`StrategyBase`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/strategy_base.pyx) class, which is derived from the [`TimeIterator`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/strategy_base.pyx) class.

The concrete strategy classes included with Hummingbot, including [`ArbitrageStrategy`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/arbitrage/arbitrage.pyx), [`CrossExchangeMarketMakingStrategy`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/cross_exchange_market_making/cross_exchange_market_making.pyx), [`PureMarketMakingStrategy`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/pure_market_making/pure_market_making_v2.pyx) and [`DiscoveryStrategy`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/discovery/discovery.pyx) - are all child classes of `StrategyBase`.

Each `StrategyBase` object may be managing multiple [`MarketBase`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/market_base.pyx) and [`WalletBase`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/wallet/wallet_base.pyx) objects.

### How It Works

All strategy modules are child classes of [`TimeIterator`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/strategy_base.pyx), which is called via `c_tick()` every second.

What this means is, a running strategy module is called every second via its `c_tick()` method to check on the markets and wallets, and decide whether it should perform any trades or not. One way to think about it is that a strategy module acts like it's watching a movie frame-by-frame via `c_tick()`, and reacts to what it sees in real time via trading actions.

If you're reading or writing a strategy module, the `c_tick()` function should be treated as the entry point of a strategy module. If you're reading a strategy module's code, `c_tick()` should be where you start. If you're writing a new strategy module, `c_tick()` is also going to where you start writing the important bits of your strategy.

### Markets

Each `StrategyBase` object may be associated with multiple markets.

- `cdef c_add_markets(self, list markets)`

    Associates a list of `MarketBase` objects to this `StrategyBase` object.

- `cdef c_remove_markets(self, list markets)`

    Disassociates a list of `MarketBase` objects from this `StrategyBase` object.

- `active_markets` property

    List of `MarketBase` objects currently associated with this `StrategyBase` object.

### Market Events Interface

The `StrategyBase` class comes with a set of interfaces functions for handling market events from associated `MarketBase` objects, which may be overridded by child classes to receive and process market events.

The event interface functions are as follows:

- `cdef c_did_create_buy_order(self, object order_created_event)`

    A buy order has been created. Argument is a [`BuyOrderCreatedEvent`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py) object.

- `cdef c_did_create_sell_order(self, object order_created_event)`

    A sell order has been created. Argument is a [`SellOrderCreatedEvent`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py) object.

- `cdef c_did_fill_order(self, object order_filled_event)`

    An order has been filled in the market. Argument is a [`OrderFilledEvent`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py) object.

- `cdef c_did_fail_order(self, object order_failed_event)`

    An order has failed in the market. Argument is a [`MarketOrderFailureEvent`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py) object.

- `cdef c_did_cancel_order(self, object cancelled_event)`

    An order has been cancelled. Argument is a [`OrderCancelledEvent`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py) object.

- `cdef c_did_expire_order(self, object expired_event)`

    An order has expired. Argument is a [`OrderExpiredEvent`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py) object.

- `cdef c_did_complete_buy_order(self, object order_completed_event)`

    A buy order has been completely filled. Argument is a [`BuyOrderCompletedEvent`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py) object.

- `cdef c_did_complete_sell_order(self, object order_completed_event)`

    A sell order has been completely filled. Argument is a [`SellOrderCompletedEvent`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py) object.

### Creating and Cancelling Orders

`StrategyBase` includes pre-defined logic for creating and cancelling trading orders - which are the primary ways for a strategy to interact with associated markets.

It is highly encouraged to use these functions to create and remove orders, rather than calling functions like `c_buy()` and `c_sell()` on `MarketBase` objects directly - since the functions from `StrategyBase` provides order tracking functionalities as well.

- `cdef str c_buy_with_specific_market(self, object market_symbol_pair, object amount,
                                       object order_type = *, object price = *, double expiration_seconds = *)`

- `cdef str c_sell_with_specific_market(self, object market_symbol_pair, object amount,
                                        object order_type = *, object price = *, double expiration_seconds = *)`

    Creates a buy or a sell order in the market specified by `market_symbol_pair`, returns the order ID string.

    Arguments:

    - `market_symbol_pair`: a [`MarketSymbolPair`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/market_symbol_pair.py) object specifying the `MarketBase` object and market symbol to create the order for.
    - `amount`: a `Decimal` object, specifying the order size in terms of the base asset.
    - `order_type`: an optional [`OrderType`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py) enum specifying the order type. Default value is `OrderType.MARKET`.
    - `price`: an optional `Decimal` object, specifying the price for a limit order. This parameter is ignored if `order_type` is not `OrderType.LIMIT`.
    - `expiration_seconds`: an optional number, which specifies how long a limit should automatically expire. This is mostly only used by decentralized exchanges like RadarRelay, where active order cancellation costs gas and thus passive order cancellation via expiration is preferred.


- `cdef c_cancel_order(self, object market_pair, str order_id)`

    Cancels an active order from a market.

    Arguments:

    - `market_pair`: a `MarketSymbolPair` object specifying the `MarketBase` object and market symbol to cancel order from.
    - `order_id`: Order ID string returned from a previous call to order creation functions above.

### Order Tracking

Each `StrategyBase` object comes with an internal attribute `_sb_order_tracker`, which is an [`OrderTracker`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/order_tracker.pyx) object. The `OrderTracker` object is responsible for tracking all active and in-flight orders created by the `StrategyBase` object, and also all in-flight order cancels.

![StrategyBase and order tracker](/assets/img/strategy-order-tracker.svg)

When writing or modifying a strategy module, you can use the built-in `OrderTracker` object to query the active or in-flight orders / cancels you currently have. It's useful for preventing issuing duplicate orders or order cancels.

Below are some of the user functions or properties under `OrderTracker` that you can use:

- `active_maker_orders` property

    Returns a list of still active limit orders, with their market object.

    Return type: `List[Tuple[MarketBase, LimitOrder]]`

- `market_pair_to_active_orders` property

    Returns a dictionary mapping from market symbol pairs to lists of active limit orders.

    Return type: `Dict[MarketSymbolPair, List[LimitOrder]]`

- `active_bids` property

    Returns a list of active limit bid orders, with their market object.

    Return type: `List[Tuple[MarketBase, LimitOrder]]`

- `active_asks` property

    Returns a list of active limit ask orders, with their market object.

    Return type: `List[Tuple[MarketBase, LimitOrder]]`

- `tracked_taker_orders` property

    Returns a list of in-flight or active market orders, with their market object. This is useful for decentralized exchanges where market orders may take a minute to settle due to block delay.

    Return type: `List[Tuple[MarketBase, MarketOrder]]`

- `in_flight_cancels` property

    Returns a dictionary of order IDs that are being cancelled.

    Return type: `Dict[str, float]`


## Pure Market Making

### Architecture

The built-in pure market making strategy in Hummingbot periodically requests limit order proposals from configurable order pricing and sizing plugins, and also periodically refreshes the orders by cancelling existing limit orders.

Here's a high level view of the logic flow inside the built-in pure market making strategy.

![Figure 5: Pure market making strategy logical flowchart](/assets/img/pure-mm-flowchart.svg)

The pure market making strategy operates in a tick-by-tick manner, as described in the [Strategies Overview](/strategies) document. Each tick is typically 1 second, although it can be programmatically modified to longer or shorter durations.

At each tick, the pure market making strategy would first query the order filter plugin whether to proceed or not. Assuming the answer is yes, then it'll query the order pricing and sizing plugins and calculate whether and what market making orders it should emit. At the same time, it'll also look at any existing limit orders it previously placed on the market and decide whether it should cancel those.

The process repeats over and over at each tick, causing limit orders to be periodically placed and cancelled according to the proposals made by the order pricing and sizing plugins.

### Plugins

There are a few plugin interfaces that the pure market making strategy depends on arriving at its order proposals.

![Figure 6: Pure market making strategy plugins](/assets/img/pure-mm-uml.svg)

* [`OrderFilterDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/order_filter_delegate.pxd)

    Makes the Yes / No decision to proceed with processing the current clock tick or not.

* [`OrderPricingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/order_pricing_delegate.pxd)

    Returns a [`PriceProposal`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/data_types.py) with lists of prices for creating bid and ask orders. If no order should be created at the current clock tick (e.g. because there're already existing orders), it may choose to return empty lists instead.

* [`OrderSizingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/order_sizing_delegate.pxd)

    Returns a [`SizingProposal`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/data_types.py) with lists of order sizes for creating bid and ask orders, given the pricing proposal. If a proposed order at a certain price should not be created (e.g. there's not enough balance on the exchange), it may choose to return zero size for that order instead.

### Built-in Plugins

If you configure the pure market making strategy with multiple orders **disabled**, then Hummingbot will be using [`ConstantSpreadPricingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/constant_spread_pricing_delegate.pyx) and [`ConstantSizeSizingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/constant_size_sizing_delegate.pyx) for the pricing and sizing plugins.

#### ConstantSpreadPricingDelegate

If you look into the logic of the [`ConstantSpreadPricingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/constant_spread_pricing_delegate.pyx), it's extremely simple - it'll always propose a bid and an ask order at a pre-configured spread from the current mid-price. It doesn't do any checks about whether you have existing orders, or have enough balance to create the orders - but that's fine.

#### ConstantSizeSizingDelegate

The logic inside [`ConstantSizeSizingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/constant_size_sizing_delegate.pyx) looks a bit more involved, because it's checking whether there're existing limit orders that are still active, and also whether there's enough balance in the exchange to create new orders. But beyond the checks, it's really just proposing constant order size proposals.

If all the checks are green (i.e. no active limit orders, and enough balance to make new orders), then it will make an order size proposal with the pre-configured size on both the bid and ask sides. Otherwise, it'll propose 0 order sizes.

If you configure the pure market making strategy with multiple orders **enabled**, then Hummingbot will be using [`ConstantMultipleSpreadPricingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/constant_multiple_spread_pricing_delegate.pyx) and [`StaggeredMultipleSizeSizingDelegate`](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/pure_market_making/staggered_multiple_size_sizing_delegate.pyx) for the pricing and sizing plugins instead.

### Refreshing orders periodically

For each limit order that was emitted by the pure market making strategy, an expiry timestamp would be generated for that order and the order will be tracked by the strategy. The time until expiry for new orders is configured via the **cancel_order_wait_time** option in [Configuration Parameters](#configuration-parameters).

Once an order's expiration time has passed, the pure market making strategy will create a cancel order proposal for that order.

### Executing order proposals

After collecting all the order pricing, sizing and cancel order proposals from plugins and the internal refresh order logic - the pure market making strategy logic will merge all of the proposals and execute them.

### Example Order Flow

Below is a hypothetical example of how the pure market making strategy works for a few clock ticks.

At clock tick *n*, there may be existing limit orders on both the bid and ask sides, and both have not yet expired. Assuming we're using the `ConstantSizeSizingDelegate` and `ConstantSpreadPricingDelegate` in this case, the proposed sizes for new orders will be 0. There'll be no cancel order proposals. So the strategy will do nothing for this clock tick.

At clock tick *n+1*, the limit bid order has expired. The strategy will then generate a cancel order proposal for the expired bid order. The cancellation will then be send to the exchange and executed.

At clock tick *n+2*, the `ConstantSizeSizingDelegate` notices there's no longer an order at the bid side. So it'll propose a non-zero order size for a new bid order. Let's assume the existing ask order hasn't expired yet, so no cancellation proposals will be generated at this clock tick. At the execution phase, the strategy will simply create a bid order calculated from the current market mid-price. Thus the bid order is refreshed.

This cycle of order creation and order cancellation will repeat again and again for as long as the strategy is running. If a limit order is completely filled by a market order, the strategy will simply refresh it at the next clock tick.
