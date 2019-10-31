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

Integrating your own data source component would require you to extend from the `OrderBookTrackerDataSource` base class [here](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/data_type/order_book_tracker_data_source.py).

The table below details the **required** functions in `OrderBookTrackerDataSource`:

Function<div style="width:200px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`get_active_exchange_markets` | None | `pandas.DataFrame` | Performs the necessary API request(s) to get all currently active trading pairs on the exchange and returns a `pandas.DataFrame` with each row representing one active trading pair.<br/><br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: If none of the API requests returns a traded `USDVolume` of a trading pair, you are required to calculate it and include it as a column in the `DataFrame`.<br/><br/>Also the the base and quote currency should be represented under the `baseAsset` and `quoteAsset` columns respectively in the `DataFrame`</td></tr></tbody></table>
`get_trading_pairs` | None | `List[str]` | Calls `get_active_exchange_market` to retrieve a list of active trading pairs.<br/><br/>Ensure that all trading pairs are in the right format.
`get_snapshot` | client: `aiohttp.ClientSession`, trading_pair: `str` | `Dict[str, any]` | Fetches order book snapshot for a particular trading pair from the exchange REST API. <table><tbody><tr><td bgcolor="#ecf3ff">**Note**: Certain exchanges do not add a timestamp/nonce to the snapshot response. In this case, to maintain a real-time order book would require generating a timestamp for every order book snapshot and delta messages received and applying them accordingly.<br/><br/>In [Bittrex](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/bittrex/bittrex_api_order_book_data_source.py), this is performed by invoking the `queryExchangeState` topic on the SignalR WebSocket client.</td></tr></tbody></table>
`get_tracking_pairs` | None | `Dict[str, OrderBookTrackerEntry]` | Initializes order books and order book trackers for the list of trading pairs. 
`listen_for_trades` | ev_loop: `asyncio.BaseEventLoop`, output: `asyncio.Queue` | None | Subscribes to the trade channel of the exchange. Adds incoming messages(of filled orders) to the `output` queue, to be processed by 
`listen_for_order_book_diffs` | ev_loop: `asyncio.BaseEventLoop`, output: `asyncio.Queue` | None | Fetches or Subscribes to the order book snapshots for each trading pair. Additionally, parses the incoming message into a `OrderBookMessage` and appends it into the `output` Queue.
`listen_for_order_book_snapshots` | ev_loop: `asyncio.BaseEventLoop`, output: `asyncio.Queue` | None | Fetches or Subscribes to the order book deltas(diffs) for each trading pair. Additionally, parses the incoming message into a `OrderBookMessage` and appends it into the `output` Queue.

### ActiveOrderTracker

The `ActiveOrderTracker` class is responsible for parsing raw data responses from the exchanges API servers.<br/> This is **not** required on all exchange connectors depending on API responses from the exchanges. This class is mainly used by DEXes to facilitate the tracking of orders

The table below details the **required** functions in `ActiveOrderTracker`:

Function<div style="width:150px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`active_asks` | None | `Dict[Decimal, Dict[str, Dict[str, any]]]` | Get all asks on the order book in dictionary format.
`active_bids` | None | `Dict[Decimal, Dict[str, Dict[str, any]]]` | Get all bids on the order book in dictionary format.
`convert_snapshot_message_to_order_book_row` | `object`: message | ```Tuple[List[OrderBookRow],List[OrderBookRow]]``` | Convert an incoming snapshot message to Tuple of `np.arrays`, and then convert to `OrderBookRow`.
`convert_diff_message_to_order_book_row` | `object`: message | `Tuple[List[OrderBookRow],List[OrderBookRow]]` | Convert an incoming diff message to Tuple of `np.arrays`, and then convert to `OrderBookRow`.
`convert_trade_message_to_order_book_row` | `object`: message | `Tuple[List[OrderBookRow],List[OrderBookRow]]` | Convert an incoming trade message to Tuple of `np.arrays`, and then convert to `OrderBookRow`.
`c_convert_snapshot_message_to_np_arrays` | `object`: message | `Tuple[numpy.array, numpy.array]` | Parses an incoming snapshot messages into `numpy.array` data type to be used by `convert_snapshot_message_to_order_book_row()`.
`c_convert_diff_message_to_np_arrays` | `object`: message | `Tuple[numpy.array, numpy.array]` | Parses an incoming delta("diff") messages into `numpy.array` data type to be used by `convert_diff_message_to_order_book_row()`.
`c_convert_trade_message_to_np_arrays` | `object`: message | `numpy.array` | Parses an incoming trade messages into `numpy.array` data type to be used by `convert_diff_message_to_order_book_row()`.

!!! warning
    `OrderBookRow` should only be used in the `ActiveOrderTracker` class, while `ClientOrderBookRow` should only be used in the `Market` class. The reason for this has to do with performance when dealing with the `OrderBook` and we will only convert the `float` to a `Decimal` when the Hummingbot client uses it.

### OrderBookTracker

The `OrderBookTracker` class is responsible for maintaining a real-time order book on the Hummingbot client. By using the subsidiary classes like `OrderBookTrackerDataSource` and `ActiveOrderTracker`(as required), it applies the market snapshot/delta messages onto the order book.

Integrating your own tracker would require you to extend from the `OrderBookTracker` base class [here](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/data_type/order_book_tracker.py).

The table below details the **required** functions to be implemented in `OrderBookTracker`:

Function<div style="width:200px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`data_source` | None | `OrderBookTrackerDataSource` | Retrieves the `OrderBookTrackerDataSource` object for this `OrderBookTracker`.
`exchange_name` | None | `str` | Returns the exchange name.
`_refresh_tracking_tasks` | None | None | Starts tracking for any new trading pairs, and stop tracking for any inactive trading pairs.<br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: Requires the `get_tracking_pairs()` function from data source to obtain the available pairs on the exchange. </td></tr></tbody></table>
`_order_book_diff_router` | None | None | Route the real-time order book diff messages to the correct order book.<br/><br/>Each tracked trading pair has their own `_saved_message_queues`, this would subsequently be used by `_track_single_book` to apply the messages onto the respective order book.
`_order_book_snapshot_router` | None | None | Route the real-time order book snapshot messages to the correct order book.<br/><br/>Each tracked trading pair has their own `_saved_message_queues`, this would subsequently be used by `_track_single_book` to apply the messages onto the respective order book.
`_track_single_book` | None | None | Update an order book with changes from the latest batch of received messages.<br/>Constantly attempts to retrieve the next available message from `_save_message_queues` and applying the message onto the respective order book.<br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: Might require `convert_[snapshot|diff]_message_to_order_book_row` from the `ActiveOrderTracker` to convert the messages into `OrderBookRow`</td></tr></tbody></table>
`start` | None | None | Start all custom listeners and tasks in the `OrderBookTracker` component. <table><tbody><tr><td bgcolor="#ecf3ff">**Note**: You may be required to call `start` in the base class by using `await super().start()`. This is **optional** as long as there is a task listening for trade messages and emitting the `TradeEvent` as seen in `c_apply_trade` in [`OrderBook`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/data_type/order_book.pyx) </td></tr></tbody></table>

#### Additional Useful Function(s)

The table below details some functions already implemented in the [`OrderBookTracker`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/data_type/order_book_tracker.py) base class:

Function<div style="width:150px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`order_books` | None | `Dict[str, OrderBook]` | Retrieves all the order books being tracked by `OrderBookTracker`.
`ready` | None | `bool` | Returns a boolean variable to determine if the `OrderBookTracker` is in a state such that the Hummingbot client can begin its operations.
`snapshot` | None | `Dict[str, Tuple[pd.DataFrame, pd.DataFrame]]` | Returns the bids and asks entries in the order book of the respective trading pairs.
`start` | None | None | Start listening on trade messages. <table><tbody><tr><td bgcolor="#ecf3ff">**Note**: This is to be overridden and called by running `super().start()` in the custom implementation of `start`.</td></tr></tbody></table>
`stop` | None | None | Stops all tasks in `OrderBookTracker`.
`_emit_trade_event_loop` | None | None | Attempts to retrieve trade_messages from the Queue `_order_book_trade_stream` and apply the trade onto the respective order book.

## Task 2. User Stream Tracker

The `UserStreamTracker` main responsibility is to fetch user account data and process it accordingly since the Hummingbot client has to manage each user's available balances and their open orders on the various exchanges to effective manage orders.

`UserStreamTracker` contains subsidiary classes that help maintain the real-time wallet/holdings balance and open orders of a user. Namely, the classes required are `UserStreamTrackerDataSource`, `UserStreamTracker` and `MarketAuth`(if applicable).

!!! note
    This is only required in **Centralized Exchanges**.

### UserStreamTrackerDataSource

The `UserStreamTrackerDataSource` class is responsible for making API calls and/or WebSocket queries to obtain order book snapshots, order book deltas and miscellaneous information on order book.

Integrating your own data source component would require you to extend from the OrderBookTrackerDataSource base class here.

The table below details the **required** functions in `UserStreamTrackerDataSource`:

Function<div style="width:200px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`order_book_class` | None | `OrderBook` | Get relevant order book class ot access class specific methods.<br/><br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: You are also required to implement your own `OrderBook` class that converts JSON data into a standard `OrderBookMessage` format.</td></tr></tbody></table>
`listen_for_user_stream` | ev_loop: `asyncio.BaseEventLoop`<br/>output: `asyncio.Queue` | None | Subscribe to user stream via web socket, and keep the connection open for incoming messages

### UserStreamTracker

The `UserStreamTracker` class is responsible for maintaining the real-time account balances and orders of the user. 

This can be achieved in 2 ways(depending on the available API on the exchange):

1. **REST API**

    In this scenario, we would have to periodically make API requests to the exchange to retrieve information on the user's **account balances** and **order statuses**.
    An example of this can be seen in the [Huobi](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/huobi/huobi_market.pyx) connector.

2. **WebSocket API**

    When the exchange does have WebSocket API support for retrieve user account details and order statuses, it would be ideal to have incorporate it into the Hummingbot client when managing account balances and updating order statuses. This is especially important since Hummingbot needs knows what are the available account balances and order statuses at all times. 
    
    !!! tip 
        In most scenarios, as seen in most other Centralized Exchanges([Binance](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/binance/binance_user_stream_tracker.py), [Coinbase Pro](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/coinbase_pro/coinbase_pro_user_stream_tracker.py), [Bittrex](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/bittrex/bittrex_user_stream_tracker.py)), a simple WebSocket integration is used to listen on selected topics and retrieving messages to be processed in `Market` class, where the messages are applied to `_available_balances`, `_account_available_balances` and triggering the necessary `Events`.

The table below details the **required** functions to be implemented in `UserStreamTracker`:

Function<div style="width:200px"/> | Input Parameter(s) | Expected Output(s)(s) | Description
---|---|---|---
`data_source` | None | `UserStreamTrackerDataSource` | Initializes a user stream data source (user specific order deltas from a websocket stream)
`start` | None | None | Starts all listeners and tasks
`user_stream` | None | `asyncio.Queue` | Returns the message queue containing all the messages pertaining to user account balances and order statues.
 
### Authentication

The `Auth` class is responsible for crafting the request parameters and bodies that are necessary for certain API requests.

For a more detailed explanation and implementation details, please refer to the [Authentication](#task-3-market-connector) section in the Task 3.

## Task 3. Market Connector

The primary bulk of integrating a new exchange connector is in the section. 

The role of the `Market` class can be broken down into placing and tracking orders. Although this might seem pretty straightforward, it does require a certain level of understanding and knowing the expected side-effect(s) of certain functions.

Before we get started, placing of orders and other user specific interactions require `Authentication`.

### Authentication

Placing and tracking of orders on the exchange normally requiring a form of authentication tied to every requests to ensure protected access/actions to the assets that users have on the respective exchanges. 

As such, it is would only make sense to have a module dedicated to handling authentication.

As briefly mentioned, the `Auth` class is responsible for creating the request parameters and/or data bodies necessary to authenticate an API request.

!!! note
    Mainly used in the `Market` class, but may be required in the `UserStreamTrackerDataSource` to authenticate subscribing to a WebSocket connection in [`listen_for_user_stream`](#userstreamtrackerdatasource).

Function<div style="width:150px"/> | Input Parameter(s) | Expected Output(s)(s) | Description
---|---|---|---
`generate_auth_dict` | http_method: `str`,<br/>url: `str`,<br/>params: `Dict[str, any]`,<br/>body: `Dict[str, any]` | `Dict[str, any]` | Generates the url and the valid signature to authenticate a particular API request.

!!! tip
    The **input parameters** and **return** value(s) can be modified accordingly to suit the exchange connectors. In most cases, the above parameters are required when creating a signature.

### Market

The section below will describe the in detail what is required for the `Market` class to place and track orders.

#### Placing Orders
 
The `execute_buy` and `execute_sell` are the crucial functions when placing orders on the exchange, below will describe the task of these function.

Function<div style="width:150px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`execute_buy` | order_id: `str`,<br/>symbol: `str`,<br/>amount: `Decimal`,<br/>order_type: `OrderType`,<br/>price: `Optional[Decimal] = s_decimal_0`| None | Function that takes the strategy inputs, auto corrects itself with trading rules, and places a buy order by calling the `place_order` function.<br/><br/>This function also begins to track the order by calling the `c_start_tracking_order` and `c_trigger_event` function.<br/>
`execute_buy` | order_id: `str`,<br/>symbol: `str`,<br/>amount: `Decimal`,<br/>order_type: `OrderType`,<br/>price: `Optional[Decimal] = s_decimal_0` | None | Function that takes the strategy inputs, auto corrects itself with trading rules, and places a buy order by calling the `place_order` function.

!!! warning
    The `execute_buy` and `execute_sell` methods verify that the trades would be legal given the trading rules pulled from the exchange and calculate applicable trading fees. They then must do the following:
    
    - Quantize the order amount to ensure that the precision is as required by the exchange
    - Create a `params` dictionary with the necessary parameters for the desired order
    - Pass the `params` to an `Auth` object to generate the signature and place the order
    - Pass the resulting order ID and status along with the details of the order to an `InFlightOrder`
    
    `InFlightOrders` are stored within a list in the `Market` class, and are Hummingbot’s internal records of orders it has placed that remain open on the market. When such orders are either filled or canceled, they are removed from the list and the relevant event completion flag is passed to the strategy module.

Considering that placing of orders normally involves a `POST` request to a particular buy/sell order REST API endpoint. This would **require** additional parameters like :

Variable(s)<div style="width:100px"/>  | Type                | Description
-------------|---------------------|-------------
`order-id`   | `str`               | A generated, client-side order ID that will be used to identify an order by the Hummingbot client.<br/> The `order_id` is generated in the `c_buy` function.
`symbol`     | `str`               | The trading pair string representing the market on which the order should be placed. i.e. (ZRX-ETH) <br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: Some exchanges have the trading pair symbol in `Quote-Base` format. Hummingbot requires that all trading pairs to be in `Base-Quote` format.</td></tr></tbody></table>
`amount`     | `Decimal`           | The total value, in base currency, to buy/sell.
`order_type` | `OrderType`         | OrderType.LIMIT or OrderType.MARKET
`price`      | `Optional[Decimal]` | If `order_type` is `LIMIT`, it represents the rate at which the `amount` base currency is being bought/sold at. `s_decimal_0` <br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: `s_decimal_0 = Decimal(0)` </td></tr></tbody></table>

#### Cancelling Orders

The `execute_cancel` function is the primary function used to cancel any particular tracked order. Below is a quick overview of the `execute_cancel` function

Function<div style="width:150px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`execute_cancel` | symbol: `str`,<br/>order_id: `str` | order_id: `str` | Function that makes API request to cancel an active order and returns the order_id if it has been successfully cancelled.<br/><br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: This function also stops tracking the order by calling the `c_stop_tracking_order` and `c_trigger_event` functions.</td></tr></tbody></table>

!!! note
    The `execute_cancel` function also stops tracking orders(`c_stop_tracking_order`) that are **not open** on the exchange.
   

#### Tracking Orders

#### Additional Function(s)

Below are a list of `required` functions for the `Market` class to be fully functional.

Function<div style="width:150px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---


## Task 4. Hummingbot Client
Coming soon...

## Additional: Debugging & Testing
Coming soon...

### Option 1. aiopython console

### Option 2. Custom Scripts

### Option 3. Unit Test Cases

## Examples / Templates

Please refer to [Examples / Templates](/developers/connectors/#examples-templates) for some existing reference when implementing a connector.


