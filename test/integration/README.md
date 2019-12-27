# General plan for integration testing of a connector

## Public APIs

### Order book tracker

#### Order book integrity

This series of tests verifies the correctness of stored in memory order book:

* Setup volume1 and volume2 so that volume1 is the minimal traded volume, and volume2 = volume1 * 1000

##### Spread correctness
The test verifies that best bid price is less than best ask price.

##### Buy slippage correctness
In this test we use stored order book to calculate cost of buying minimal traded volume (volume1) and volume2. The connector exposes entry point called `get_price_for_volume`, which performs this calculation.

In the connector cost of buying volume2 is calculated by means of adding several orders in the order book. Let's say the orders are numbered from 0 to N, the price of i-th order is p[i] and the volume of i-th order is v[i]. In order to find the total cost, the connector should use formula:

cost = sum(p[i]*v[i])

where i iterates from 0 until the sum(v[i]) is equal to volume2. The last element of v[i] must be reduced for this formula if the resulting sum if greater than volume2, which reflects partial execution of the i-th order.

Because of slippage costs to buy volume1 and cost to buy volume2 may be different, but the cost to buy volume2 should be never less than cost to buy volume1.

* Cost to buy volume1 is less or equal than price to buy volume2

##### Sell slippage correctness
In this test we use stored order book to calculate cost of selling minimal traded volume (volume1) and volume2. Because of slippage these two costs may be different, but cost to sell volume2 should be never greater than cost to sell volume1.

* Cost to sell volume1 is greater or equal than price to sell volume2

### Get trades

#### Order book tracker receives trades and emits correct trade events

## Rate limit

### Comply with rate limit
* API allows to send public requests at allowed rate limit

### Exceed rate limit
* API does not allow to send public requests above allowed rate limit

## Get fees

## Placing market orders

### Place buy market order

### Place sell market order

## Placing limit orders

### Place buy limit order at considerable distance from best price
* Place buy limit order
* Wait until order is registered on exchange
* Read orders - the order should be seen
* Cancel order

### Place sell limit order at considerable distance from best price
* Place buy limit order
* Wait until order is registered on exchange
* Read orders - the order should be seen
* Cancel order

## Placing limit orders and watching completion events

### Place limit buy order and watch for completion
* Place a limit buy order at the best price
* If price moves, cancel and replace order
* Repeat until completion event is seen

### Place limit sell order and watch for completion
* Place a limit sell order at the best price
* If price moves, cancel and replace order
* Repeat until completion event is seen

## Placing and canceling all orders
* Place buy limit order at considerable distance from best price
* Cancel all orders immediately (before placed order is registered in exchange, but after it is sent)
* New order should not be placed or should appear as canceled

## Order Price and Amount Precision

* Place limit order at considerable distance from best price
* Test both buy and sell orders
* Assert that price is rounded to the nearest price quantum below the requested price
* Assert that amount is rounded to the nearest amount quantum below the requested price

The price and amount quantum must be read from the exchange. Rounding to the quantum is calculated so that the resulting number contains an integer number of quantums.

## Orders Saving and Restoration

Test name: test_orders_saving_and_restoration

* Place limit order at considerable distance from best price
* Assert that order is placed and order placed event contains same order ID as one returned by .buy or .sell method.
* Assert that .tracking_states contains one order and the order ID matches
* Assert that recorder contains one order with the matching order ID
* Assert that recorder contains market_states dict and the length of it is non-zero
* Close exchange connector (market), stop recorder
* Re-open exchange connector
* Assert that recorder contains 0 limit orders and 0 market states
* Restore tracking states in recorder (call restore_tracking_states)
* Assert that recorder contains 1 limit order and 1 market state

## Market Logger: Order Fills Saving

Test name: test_order_fill_record

* Place limit order at the best bid price
* Wait for execution event (cancel and replace order if necessary)
* Place limit order at the best ask price (to sell back)
* Wait for execution event (cancel and replace order if necessary)
* Assert that market logger (recorder.get_trades_for_config) contains 1 sell and 1 buy fill

## Withdraw Test

Test name: test_withdraw

* Start a withdraw operation (a token to an external address)
* Wait for completion event
* Assert that completion event contains correct withdrawn asset name
* Assert that completion event contains correct destination address
* Assert that completion event contains correct withdrawn amount
* Assert that completion event contains correct fee
* Assert that destination address balance increased by correct amount

## Deposit Info Test

Test name: test_deposit_info

* Setup test by sending deposit manually (one-time setup)
* Retrieve deposit info for the deposited asset
* Assert that deposit info contains non-zero address field
* Assert that deposit info contains non-zero extras field with addressTag
* Assert that deposit_info.extras['asset'] contains correct asset name

## Server Time Offset Accuracy

Test name: test_server_time_offset

* Mock market_time.time to offset time by 30 seconds from real system time
* Assert that <your exchange>_client_module.time returns time_offset_ms that matches 30 seconds with 5% precision

## User stream tracker
