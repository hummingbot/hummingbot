# Perform Trade

## Architecture

In the Perform Trade strategy, Hummingbot places a single order that is specified by the user. Unlike Simple Trade, orders aren’t cancelled after a certain amount of time and are only placed once at the start of the strategy.

Here's a high level view of the logic flow inside the built-in perform trade strategy.

![Figure 1: Perform trade strategy flow chart](/assets/img/perform-trade-flowchart.svg)

The flow of the strategy is as follows

1. Get user input
2. Sanity Checks
3. Place Order


## Sanity Checks & Validation

Before the strategy attempts to perform any trades it checks the following to ensure it is safe to perform the trade:

1. Are both markets ready and connected?
2. Does the user have enough balance? 
    1. Additionally, this check triggers a warning and logs the warning. If the user does not have the requisite balance to perform the trade, the interface will display the warning.
    2. To achieve this check, the Perform Trade strategy gets the user’s available balance by using the `c_has_enough_balance()` in [perform_trade.pyx](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/dev_2_perform_trade/dev_2_perform_trade.pyx).

## Managing Order State
Order state is tracked using the quantity, price, type, id, and other attributes. 
The OrderTracker class includes functions monitoring when order tracking begins, noticing and tracking cancels, and when tracking ends. When an order is completed an order id is returned and the specifics concerning the order can be determined by using the OrderTracker class.

The order state, specifically, whether the order is partially or completely filled is managed by events in the MarketBase class. Specifically, the logic regarding order creation, cancelation, filling, and completion can be found in the following functions in [market_base.pyx](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/market_base.pyx): `buy()`, `sell()`, `cancel()`, `get_order_price_quantum()` (gets the required or allowed order price), and `get_order_size_quantum()` (gets the required or allowed order size).

The order tracking logic can be found in the `c_start_tracking_limit_order()`, `c_stop_tracking_limit_order()`, `c_has_in_flight_cancel()` and `c_check_and_track_cancel()` function inside [order_tracker.pyx](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/order_tracker.pyx).

## Logging

The Perform Trade strategy includes logging operations for info, warnings, and errors. The info logs include information regarding transactions and is logged with severity info. The warning logs include information regarding warning during a user’s session such as insufficient balance. Finally, the error logs include error information such as the markets being down or being unable to connect to the markets and are stored with severity error.
## History
The history command displays fulfilled orders, the balance snapshot, and performance analysis.
Most importantly for this strategy, the completed trades are shown by querying the database to see which trades have occurred since the start of the session.

The logic for getting the history can be found in the balance_snapshot function and trades list inside [history_command.py](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/client/command/history_command.py) file.
