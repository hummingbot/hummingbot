# Developer Tutorial
## Introduction
This tutorial is intended to get you familiarized with basic structure of a connector in Hummingbot. It will guide you through the scope of creating/modifying the necessary components to implement a connector.

By the end of this tutorial, you should: 

* Have a general understanding of the base classes that serve as building blocks of a connector
* Be able to integrate new connectors from scratch

Implementing a new connector can generally be split into 3 major tasks, namely:<br/>
[Data Source & Order Book Tracker](#task-1-data-source-order-book-tracker), [User Stream Tracker](#task-2-user-stream-tracker) and [Market Connector](#task-3-market-connector)

## Task 1. Data Source & Order Book Tracker

Generally the first 2 components you should begin with when implementing your own connector are the `OrderBookTrackerDataSource` and `OrderBookTracker`.

The `OrderBookTracker` contains subsidiary classes that help maintain the real-time order book of a market. Namely, the classes are `OrderBookTrackerDataSource` and `ActiveOrderTracker`.

### OrderBookTrackerDataSource

The `OrderBookTrackerDataSource` class is responsible for making API calls and/or WebSocket queries to obtain order book snapshots, order book deltas and miscellaneous information on order book.

The table below details the required functions in `OrderBookTrackerDataSource`:

Function | Input Parameters | Expected Output | Description
---|---|---|---
`get_active_exchange_markets` | None | `Pandas.DataFrame` | Performs the necessary API request(s) to get all currently active trading pairs on the exchange and returns a `Pandas.DataFrame` with each row representing one active trading pair.<br/><br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: If none of the API requests returns a traded `USDVolume` of a trading pair, you are required to calculate it and include it as a column in the `DataFrame`.<br/><br/>Also the the base and quote currency should be represented under the `baseAsset` and `quoteAsset` columns respectively in the `DataFrame`</td></tr></tbody></table>
`get_trading_pairs` | None | `List[str]` | Calls `get_active_exchange_market` to retrieve a list of active trading pairs.<br/><br/>Ensure that all trading pairs are in the right format.
`get_snapshot` | client: `aiohttp.ClientSession`, trading_pair: `str` | `Dict[str, any]` | Fetches order book snapshot for a particular trading pair from the exchange REST API. <table><tbody><tr><td bgcolor="#ecf3ff">**Note**: Certain exchanges do not add a timestamp/nonce to the snapshot response. In this case, to maintain a real-time order book would require you timestamp every order book snapshot and delta messages and applying them accordingly.<br/><br/>In [Bittrex](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/bittrex/bittrex_api_order_book_data_source.py), this is performed by invoking the `queryExchangeState` topic on the SignalR WebSocket client.</td></tr></tbody></table>
`get_tracking_pairs` | None | `Dict[str, OrderBookTrackerEntry]` | Initializes order books and order book trackers for the list of trading pairs. 
`listen_for_trades` | ev_loop: `asyncio.BaseEventLoop`, output: `asyncio.Queue` | None | Subscribes to the trade channel of the exchange. Adds incoming messages(of filled orders) to the `output` queue, to be processed by 
`listen_for_order_book_diffs` | ev_loop: `asyncio.BaseEventLoop`, output: `asyncio.Queue` | None | Fetches or Subscribes to the order book snapshots for each trading pair. Additionally, parses the incoming message into a `OrderBookMessage` and appends it into the `output` Queue.
`listen_for_order_nook_snapshots` | ev_loop: `asyncio.BaseEventLoop`, output: `asyncio.Queue` | None | Fetches or Subscribes to the order book deltas(diffs) for each trading pair. Additionally, parses the incoming message into a `OrderBookMessage` and appends it into the `output` Queue.

### ActiveOrderTracker
Coming soon...


### OrderBookTracker
Coming soon...


## Task 2. User Stream Tracker
Coming soon...

## Task 3. Market Connector

### Placing and tracking orders

`Market` classes place orders via `execute_buy` and `execute_sell` commands, which require the following arguments:

- The order ID
- The market symbol
- The amount of the order
- The type (limit or market)
- The price, if limit order

The `execute_buy` and `execute_sell` methods verify that the trades would be legal given the trading rules pulled from the exchange and calculate applicable trading fees. They then must do the following:

- Quantize the order amount to ensure that the precision is as required by the exchange
- Create a `params` dictionary with the necessary parameters for the desired order
- Pass the `params` to an `Auth` object to generate the signature and place the order
- Pass the resulting order ID and status along with the details of the order to an `InFlightOrder`

`InFlightOrders` are stored within a list in the `Market` class, and are Hummingbot’s internal records of orders it has placed that remain open on the market. When such orders are either filled or canceled, they are removed from the list and the relevant event completion flag is passed to the strategy module.

## Additional: Debugging & Testing
Coming soon...

### Option 1. aiopython console

### Option 2. Custom Scripts

### Option 3. Unit Test Cases

## Examples / Templates

Please refer to [Examples / Templates](/developers/connectors/#examples-templates) for some existing reference when implementing a connector.


