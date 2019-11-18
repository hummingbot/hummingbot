# VWAP

The VWAP strategy is a common algorithmic execution strategy which allows traders to account for slippage by splitting up orders over time. Specifically, the VWAP strategy helps traders minimize slippage when buying or selling large orders. The methods utilized in VWAP make the strategy more useful to traders and will help when creating future, more complex strategies.

## Config

VWAP utilizes user input for:
* is_vwap : indicate if user wants to use VWAP or TWAP
* percent_slippage : percent amount of order price that user is willing to set aside for slippage (0.1 signifies 0.1%)
* order_percent_of_volume : percent of open order volume (at the specified price) that user wants to cap the order at (ex. user wants to cap the order volume at 0.1% of total available order volume)



## Strategy

The VWAP strategy fetches the order book and calculates the total open order volume up to percent_slippage. If no order is outstanding, an order is submitted which is capped at order_percent_of_volume * open order volume up to percent_slippage. The previous order is filled before the next is submitted and if an order is currently outstanding no action occurs.

![Figure 1: Placing orders](/assets/img/VWAP_2.svg)

Specifically, the operations in the flow chart above occur in the following sections of code:
* c_process_order():
  * Check if TWAP or VWAP
    * If VWAP, check if there is an outstanding order (self._has_outstanding_order)
    * If no outstanding order, place order using c_place_orders()
* c_place_orders():
  * Check if VWAP
  * Set order_price
    * If MARKET order => set order_price as order book’s price
    * If LIMIT order => set order_price as user specified order price (from config)
  * Set slippage_amount = order price * percent slippage
  * Set slippage_price
    * If BUY then slippage_price = order price + slippage amount because user is willing to buy for a higher price
    * If SELL then slippage_price = order price - slippage amount because user is willing to sell for a lower price
  * Get total_order_volume
    * Use OrderBook class’s c_get_volume_for_price() function to get the amount of order volume that is available for the specified slippage_price
  * Set order_cap = total order volume * order percent of volume
  * Set quantized_amount = get the minimum value between the calculated order cap and the quantity remaining from order to complete

The flow chart below details the flow of processing orders.

![Figure 1: Processing orders](/assets/img/VWAP_1.svg)

Only one order is placed in a clock tick, so a state machine is needed to emit multiple orders over different clock ticks.

The state variables for TWAP:
* self._is_vwap
* self._percent_slippage
* self._order_percent_of_volume
* self._has_outstanding_orders : keeps track of whether the user has an active order that is not yet filled
