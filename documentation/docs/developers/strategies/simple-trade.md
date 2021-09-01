# Simple Trade

## Overview

Simple trade strategy expands upon Perform Trade strategy. By the end of this part, you should be able to add:

* time delay between trades
* set a time restriction to cancel order
* implement specific loggings

## Use clock & `c_tick()` to add time restrictions

`c_tick()` : Called everytime a clock 'ticks'

* Check for readiness and connection status of markets with `_all_markets_ready`
* If all markets are ready, call `c_process_market()` on each market.
* Set `_last_timestamp` to current tick's timestamp

NOTE : Can change tick interval by specifying `_tick_size` on clock. Default = `1.0`

#### Add time delay between trades
Ensure that there is a given amount of time in between the trades.

`c_process_market()` : Called on each market from `c_tick()`

* If there is an order to place, check that current timestamp is greater than previous order's timestamp plus delay time (e.g. current timestamp > previous order's start timestamp + `_time_delay`)
* If current time is valid time to place orders, call `c_place_orders()` to execute the order

NOTE : Can change delay interval by specifying `_time_delay`. Default = `10.0`

![Figure 1: Processing a new order](/assets/img/Simple_Trade_OrderPlacedRevised.svg)

#### Set time to cancel order
Cancel orders once their elapsed times go over a certain amount.

`c_process_market()` : Called on each market from `c_tick()`

* If there are active orders, check if order needs to be canceled (e.g. current_timestamp >= order's start timestamp + `_cancel_order_wait_time`)
* If an order has to be canceled, call `c_cancel_order()` on corresponding order

NOTE : Can change cancel interval by specifying `_cancel_order_wait_time`. Default = `60.0`

![Figure 2: Cancelling an order](/assets/img/Simple_Trade_OrderCancelledRevised.svg)
 
## Logging
When a specific event about the order is triggered, the event handler calls these logging methods to provide helpful information to the users.

* `c_did_fill_order()` — Called when `OrderFilledListener` sees that an order is filled. 
* `c_did_complete_buy_order()` — Called when `BuyOrderCompletedListener` sees that a buy order is completed.
* `c_did_complete_sell_order()` — Called when `SellOrderCompletedListener` sees that a sell order is completed.

These functions check to see if the order of interest is market or limit order and outputs appropriate text for each types.

Similar mechanisms can be implemented for the following existing event listeners:
* `OrderFailedListener`
* `OrderCancelledListener`
* `OrderExpiredListener`
* `BuyOrderCreatedListener`
* `SellOrderCreatedListener`

