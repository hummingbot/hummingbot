# Task 2. User Stream Tracker

The `UserStreamTracker` responsibility is to fetch user account data and queues it accordingly.

`UserStreamTracker` contains subsidiary classes that help maintain the real-time wallet/holdings balance and open orders of a user. Namely, the classes required are:

* `UserStreamTrackerDataSource`
* `UserStreamTracker`
* `MarketAuth`(if applicable).

!!! note
    This is only required in **Centralized Exchanges**.

## UserStreamTrackerDataSource

The `UserStreamTrackerDataSource` class is responsible for initializing a WebSocket connection to obtain user related trade and balances updates.

Integrating your own data source component would require you to extend from the UserStreamTrackerDataSource base class here.

The table below details the **required** functions in `UserStreamTrackerDataSource`:

Function<div style="width:200px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`last_recv_time` | None | `float` | Should be updated(using python's time.time()) everytime a message is received from the websocket.	
`listen_for_user_stream` | ev_loop: `asyncio.BaseEventLoop`<br/>output: `asyncio.Queue` | None | Subscribe to user stream via web socket, and keep the connection open for incoming messages

## UserStreamTracker

The `UserStreamTracker` class is responsible for maintaining the real-time account balances and orders of the user. 

This can be achieved in 2 ways(depending on the available API on the exchange):

1. **REST API**

    In this scenario, we would have to periodically make API requests to the exchange to retrieve information on the user's **account balances** and **order statuses**.
    An example of this can be seen in [Huobi's connector market file](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/huobi/huobi_market.pyx) connector. The market file shows that Huobi uses REST API alone by periodically calling the market's `_update_balances()` and `_update_order_status()` through the `_status_polling_loop()`. Also, it can be seen that no user stream files exist in Huobi's connector directory.

2. **WebSocket API**

    When an exchange does have WebSocket API support to retrieve user account details and order statuses, it would be ideal to incorporate it into the Hummingbot client when managing account balances and updating order statuses. This is especially important since Hummingbot needs to knows the available account balances and order statuses at all times. 
    
    !!! tip 
        In most scenarios, as seen in most other Centralized Exchanges([Binance](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/binance/binance_user_stream_tracker.py), [Coinbase Pro](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/coinbase_pro/coinbase_pro_user_stream_tracker.py), [Bittrex](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/bittrex/bittrex_user_stream_tracker.py)), a simple WebSocket integration is used to listen on selected topics and retrieving messages to be processed in `Market` class.

The table below details the **required** functions to be implemented in `UserStreamTracker`:

Function<div style="width:200px"/> | Input Parameter(s) | Expected Output(s)(s) | Description
---|---|---|---
`data_source` | None | `UserStreamTrackerDataSource` | Initializes a user stream data source.
`start` | None | None | Starts all listeners and tasks.
`user_stream` | None | `asyncio.Queue` | Returns the message queue containing all the messages pertaining to user account balances and order statues.

## Debugging & Testing

As part of the QA process, for each tasks(Task 1 through 3) you are **required** to include the unit test cases for the code review process to begin. Refer to [Option 1: Unit Test Cases](/developers/connectors/debug&test/#option-1-unit-test-cases) to build your unit tests. 