# TWAP


The TWAP strategy is a common algorithmic execution strategy used for splitting up large orders over time. Specifically, the TWAP strategy helps traders minimize slippage when buying or selling large orders. These features make the strategy more useful to traders and will help when creating future, more complex strategies:

* Incrementing / maintaining states over clock ticks
* Quantizing (rounding down to nearest tradable value) order size
* Dividing an order into segments
* Incorporating time delays between segmented orders

## Overview

The TWAP strategy divides a large user order into chunks according to the following user configurations:

* Total order size
* number of individual orders
* time delay between orders

![Figure 1: Processing orders](/assets/img/TWAP_1.svg)

The orders are then split into tradable (quantized) amounts and executed sequentially with the indicated time delay in between orders. There is no time delay before the first order. Because only one order is placed in a clock tick, a state machine is needed to emit multiple orders over different clock ticks. To see the executed orders, type history into the command prompt.

## Config

Here are the additional user configurable parameters for the TWAP strategy (fields are added to `config_map` file):

* `time_delay` : Change the question to ask for the number of seconds to delay each individual order. (e.g. How many seconds do you want to wait between each individual order?)
* `num_individual_orders` : a new field added to the config map. It should ask for the number of individual orders that an order should be split up into. (e.g.Into how many individual orders do you want to split this order?)


## Strategy

The TWAP strategy logic is trying to split a large order into smaller ones over time, and it does that by maintaining important information about the state when processing orders by adding state variables.

Custom state variables can be added to the strategy by setting variables in the `__init__` function.

* `self._quantity_remaining` : Indicates the quantity of order left to be placed as individual orders. This state variable is updated after each order is placed and persisted throughout until the order is done processing.
* `self._first_order` : Indicates whether the current individual order is the first order.

![Figure 2: Placing orders](/assets/img/TWAP_2.svg)

TWAP processes orders when there is a remaining order quantity & the specified time_delay has passed. Specifically, some of the key elements in utilizing the remaining order quantity and time_delay are detailed below:

* If self._quantity_remaining is greater than 0 place an order
* If `self._first_order` is true, we want to place order as soon as `self._current_timestamp > self._previous_timestamp` we don't have a time delay before the first order
* If it isn't the first order, check that `self._current_timestamp > self._previous_timestamp + self._time_delay`
* Once order is placed, update self._quantity_remaining by subtracting the amount of the order just placed `curr_order_amount` : Either (total order amount)/(number of orders) or `self._quantity_remaining` depending on which is smaller
