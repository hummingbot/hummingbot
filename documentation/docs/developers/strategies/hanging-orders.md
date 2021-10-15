## Introduction
This section of the tutorial provides an overview of the 
[`HangingOrdersTracker`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/hanging_orders_tracker.py)
helper class designed to assist strategies with managing [hanging orders](/strategy-configs/hanging-orders/). It automates
a large part of the process, including renewing outdated orders and cancelling orders that have drifted too far from
the market price. 

Two examples of its usage can be found in the
[`PureMarketMakingStrategy`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/pure_market_making/pure_market_making.pyx)
and the [`AvellanedaMarketMakingStrategy`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/avellaneda_market_making/avellaneda_market_making.pyx)
strategies.

## Fundamental Concepts
An important fundamental concept to be aware of is that the tracker operates by maintaining a list of **candidate** 
hanging orders. This article will refer to that list as "the candidate list". Calling the
`update_strategy_orders_with_equivalent_orders` method will perform a check that the candidate list is synchronized
with the orders on the exchange and will effectively start tracking the hanging orders.

The most basic set of methods are the `add_order` and `remove_order` which respectively add and remove orders from the
candidate list of hanging orders. However, the `add_order` function is most likely to be used in the initialization
of the strategy, when hanging orders are retrieved from the database and registered with the tracker, while the
`remove_order` function may not have to be used at all as the responsibility of removing tracked hanging orders is
transferred to the tracker and automated away.

## Registering the Tracker
During the initialization phase, the `HangingOrdersTracker` must be registered with the connectors used by
the strategy in order to receive updates about the orders and perform its responsibilities. This is achieved by simply
calling the `register_events` method and passing a list of the relevant connectors. When the strategy is being stopped,
the tracker's `unregister_events` must be called to gracefully deregister the tracker from the connectors.

## Hanging Orders Creation Flow
When creating new orders, use the method aptly named `add_current_pairs_of_proposal_orders_executed_by_strategy`
to register the order pairs by passing them in as `CreatedPairOfOrders`. The tracker then starts listening for filled 
orders and updates the pairs accordingly.

Once the current cycle is over and the strategy is about to cancel the current orders and replace them with a new set,
calling `update_strategy_orders_with_equivalent_orders` will detect hanging orders from the currently active
`CreatedPairOrders` and add them to the candidate orders list. Subsequently, as mentioned in the 
[Fundamental Concepts](#fundamental-concepts) section, calling the`update_strategy_orders_with_equivalent_orders` method
will ensure the integrity of the candidate orders list and start tracking the hanging orders.

After this step is performed, the strategy can proceed to cancelling the orders it wants to cancel as part of the 
current cycle termination process. It simply needs to ask the tracker if a given order is a hanging order by calling the
`is_order_id_in_hanging_orders` method. If it is, the strategy doesn't need to worry about that order anymore. If it's
not, then the strategy can proceed to cancelling it.

## The Management Process
Finally, for the tracker to perform its tasks, the `process_tick` method must be called on every strategy tick. When the
method is called, the `HangingOrdersTracker` performs two tasks: first, it removes hanging orders with 
[extreme spreads](/strategy-configs/hanging-orders/#hanging_orders_cancel_pct); second, it renews orders that have passed
the max order age. To enable renewing old orders, the strategy must implement the 
[`max_order_age`](/strategy-configs/max-order-age/) attribute.
