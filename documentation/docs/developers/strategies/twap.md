# TWAP

## Overview

TWAP strategy expands upon Simple Trade strategy. By the end of this part, you should be able to : 

* Divide up an order into *n* individual orders
* Add time delay between each individual orders

## Config

Modifications for the following fields have to be made to the `config_map` file :

* `time_delay` : Change the question to ask for number of seconds to delay each individual order. (e.g. How many seconds do you want to wait between each individual order?)

* `num_individual_orders` : This is is a new field added to the config map. It should ask for number individual orders that an order should be split up into. (e.g.Into how many individual orders do you want to split this order?)

## Strategy file

`self._quantity_remaining` : Indicates quantity of order left to placed as individual orders

`self._first_order` : Indicates whether the current individual order is the first order 

`c_process_market()` : 

* Instead of using `self._place_orders` as an indicator of whether or not there is order to place, use `self._quantity_remaining` as the indicator. If the remaining balance is greater than 0, there still are individual orders to place.
* If `self._first_order` is true, we want to place order as soon as `self._current_timestamp > self._previous_timestamp` because we don't need to have a time delay for the first order - we only need delays in between inndividual orders. 
* If it isn't the first order, check that `self._current_timestamp > self._previous_timestamp + self._time_delay` to ensure there is a delay between individual orders.

![Figure 1: Processing orders](/assets/img/TWAP1.svg)

`c_place_orders()`:

* `curr_order_amount` : Decide the amount of the individual order. This should be equal to either the *(total order amount)/(number of orders)* or `self._quantity_remaining` depending on which one gives a smaller value because we don't want to overplace an order.
* `quantized_amount` : Calculate quantized order amount by passing in the individual order amount to `c_quantize_order_amount()`
* Once order is placed, update `self._quantity_remaining` by subtracting the quantized amount of individual order placed from original quantity remaining.

![Figure 2: Placing orders](/assets/img/TWAP2.svg)
