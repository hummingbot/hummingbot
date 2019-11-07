# TWAP

Unlike the previous tutorial strategies which demonstrated straight-forward tasks like adding configurations and using clock ticks to periodically perform action, this strategy will introduce you to implement a more complicated algorithm. The tools demonstrated in this strategy is : 
1) Maintaining some states over clock ticks to retain important information that will decide algorithm's next action 
2) Quantizing order size depending of user's specification of how the user wants order to be executed.

## Overview

TWAP strategy provides the guide for you to add these features : 

* Divide up an order into *n* individual orders
* Add time delay between each individual orders

Note that unlike Simple Trade strategy which places one order of entire quantity, the number of order is dynamically determined by user's input. Since one order can be placed over a single clock tick, there needs to some sort of information about order 'state' that will indicate when the order should stop.

## Config

To implement a more sophisticated algorithm, you probably want to ask the user for extra information that you need to feed into the algorithm. This can be done by adding more fields to the `config_map` file :

* `time_delay` : Change the question to ask for number of seconds to delay each individual order. (e.g. How many seconds do you want to wait between each individual order?)

* `num_individual_orders` : This is is a new field added to the config map. It should ask for number individual orders that an order should be split up into. (e.g.Into how many individual orders do you want to split this order?)

## Strategy file

Maintain important information about the state when processing orders by adding state variables. Custom state variables can be added to the strategy to by setting variables in the `__init__` function. 

* `self._quantity_remaining` : Indicates quantity of order left to placed as individual orders. This state variable is updated after each order is placed and persisted throughout until order is done processing.

* `self._first_order` : Indicates whether the current individual order is the first order. 




`c_process_market()` : Add logic about *when* you want to process orders. 

TWAP logic is to process orders when there are remaining order quantity AND specified time_delay has passed.

* Instead of using `self._place_orders` as an indicator of whether or not there is order to place, use `self._quantity_remaining` as the indicator. If the remaining balance is greater than 0, there still are individual orders to place.
* If `self._first_order` is true, we want to place order as soon as `self._current_timestamp > self._previous_timestamp` because we don't need to have a time delay for the first order - we only need delays in between inndividual orders. 
* If it isn't the first order, check that `self._current_timestamp > self._previous_timestamp + self._time_delay` to ensure there is a delay between individual orders.

![Figure 1: Processing orders](/assets/img/TWAP1.svg)

`c_place_orders()`: Add logic about *how* you want to place orders. This could include logic about how much quantity of order to place, which type of order to place, or whether or the condition to actually place an order. 

TWAP sets up so that the amount of order placed is determined by number individual orders a request is broken up into, and computes the quantized amount according to this information.

* `curr_order_amount` : Decide the amount of the individual order. This should be equal to either the *(total order amount)/(number of orders)* or `self._quantity_remaining` depending on which one gives a smaller value because we don't want to overplace an order.
* `quantized_amount` : Calculate quantized order amount by passing in the individual order amount to `c_quantize_order_amount()`
* Once order is placed, update `self._quantity_remaining` by subtracting the quantized amount of individual order placed from original quantity remaining.

![Figure 2: Placing orders](/assets/img/TWAP2.svg)
