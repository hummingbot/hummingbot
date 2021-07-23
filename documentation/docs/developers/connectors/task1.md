# Task 1. Data Source & Order Book Tracker

The first 2 components to begin:

 * `OrderBookTrackerDataSource`
 * `OrderBookTracker`.

The `OrderBookTracker` contains subsidiary classes that help maintain the real-time order book of a market. Namely, the classes are `OrderBookTrackerDataSource` and `ActiveOrderTracker`.

## OrderBookTrackerDataSource

The `OrderBookTrackerDataSource` class is responsible for making API calls and/or WebSocket queries to obtain order book snapshots, order book deltas, and miscellaneous information on order book.

Integrating your own data source component requires you to extend from the `OrderBookTrackerDataSource` base class [here](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/data_type/order_book_tracker_data_source.py).

The table below details the **required** functions in `OrderBookTrackerDataSource`:

Function<div style="width:200px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`get_last_traded_prices` | trading_pairs: List[str] | `Dict[str, float]` | Performs the necessary API request(s) to get last traded price for the given markets (trading_pairs) and return a dictionary of trading_pair and last traded price.
`get_snapshot` | client: `aiohttp.ClientSession`, trading_pair: `str` | `Dict[str, any]` | Fetches order book snapshot for a particular trading pair from the exchange REST API. <table><tbody><tr><td bgcolor="#ecf3ff">**Note**: Certain exchanges do not add a timestamp/nonce to the snapshot response. In this case, to maintain a real-time order book would require generating a timestamp for every order book snapshot and delta messages received and applying them accordingly.<br/><br/>In [Bittrex](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/bittrex/bittrex_api_order_book_data_source.py), this is performed by invoking the `queryExchangeState` topic on the SignalR WebSocket client.</td></tr></tbody></table>
`get_new_order_book` | trading_pair: `str` | `OrderBook` | Creates a new order book instance and populate its `bids` and `asks` by applying the order_book snapshot to the order book, you might need to involve `ActiveOrderTracker` below.
`listen_for_trades` | ev_loop: `asyncio.BaseEventLoop`, output: `asyncio.Queue` | None | Subscribes to the trade channel of the exchange. Adds incoming messages(of filled orders) to the `output` queue, to be processed by `OrderBookTracker` (in `_emit_trade_event_loop`)
`listen_for_order_book_diffs` | ev_loop: `asyncio.BaseEventLoop`, output: `asyncio.Queue` | None | Fetches or Subscribes to the order book snapshots for each trading pair. Additionally, parses the incoming message into a `OrderBookMessage` and appends it into the `output` Queue.
`listen_for_order_book_snapshots` | ev_loop: `asyncio.BaseEventLoop`, output: `asyncio.Queue` | None | Fetches or Subscribes to the order book deltas(diffs) for each trading pair. Additionally, parses the incoming message into a `OrderBookMessage` and appends it into the `output` Queue.
`get_mid_price` | trading_pair: `str` | `Decimal` | Calculates and return the average of the best bid and best ask prices from the exchange's ticker endpoint i.e `(best_bid + best_ask) / 2`
`fetch_trading_pairs` | None | `List[str]` | Return a list of supported trading pairs on the exchange. Note that pairs should be in `[Base]-[Quote]` format. And the conversion methods mentioned in Task 4 of this documentation should be used to convert pair if necessary.

## ActiveOrderTracker

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
    `OrderBookRow` should only be used in the `ActiveOrderTracker` class, while `ClientOrderBookRow` should only be used in the `Market` class. This is due to improve performance especially since calculations in `float` fair better than that of `Decimal`.

## OrderBookTracker

The `OrderBookTracker` class is responsible for maintaining a real-time order book on the Hummingbot client. By using the subsidiary classes like `OrderBookTrackerDataSource` and `ActiveOrderTracker`(as required), it applies the market snapshot/delta messages onto the order book.

Integrating your own tracker would require you to extend from the `OrderBookTracker` base class [here](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/data_type/order_book_tracker.py).

The table below details the **required** functions to be implemented in `OrderBookTracker`:

Function<div style="width:200px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`exchange_name` | None | `str` | Returns the exchange name.
`_order_book_diff_router` | None | None | Route the real-time order book diff messages to the correct order book.<br/><br/>Each trading pair has their own `_saved_message_queues`, this would subsequently be used by `_track_single_book` to apply the messages onto the respective order book.
`_order_book_snapshot_router` | None | None | Route the real-time order book snapshot messages to the correct order book.<br/><br/>Each trading pair has their own `_saved_message_queues`, this would subsequently be used by `_track_single_book` to apply the messages onto the respective order book.
`_track_single_book` | None | None | Update an order book with changes from the latest batch of received messages.<br/>Constantly attempts to retrieve the next available message from `_save_message_queues` and applying the message onto the respective order book.<br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: Might require `convert_[snapshot/diff]_message_to_order_book_row` from the `ActiveOrderTracker` to convert the messages into `OrderBookRow` </td></tr></tbody></table>
`start` | None | None | Start all custom listeners and tasks in the `OrderBookTracker` component. <table><tbody><tr><td bgcolor="#ecf3ff">**Note**: You may be required to call `start` in the base class by using `await super().start()`. This is **optional** as long as there is a task listening for trade messages and emitting the `TradeEvent` as seen in `c_apply_trade` in [`OrderBook`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/data_type/order_book.pyx) </td></tr></tbody></table>

### Additional Useful Function(s)

The table below details some functions already implemented in the [`OrderBookTracker`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/data_type/order_book_tracker.py) base class:

Function<div style="width:150px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`order_books` | None | `Dict[str, OrderBook]` | Retrieves all the order books being tracked by `OrderBookTracker`.
`ready` | None | `bool` | Returns a boolean variable to determine if the `OrderBookTracker` is in a state such that the Hummingbot client can begin its operations.
`snapshot` | None | `Dict[str, Tuple[pd.DataFrame, pd.DataFrame]]` | Returns the bids and asks entries in the order book of the respective trading pairs.
`start` | None | None | Start listening on trade messages. <table><tbody><tr><td bgcolor="#ecf3ff">**Note**: This is to be overridden and called by running `super().start()` in the custom implementation of `start`.</td></tr></tbody></table>
`stop` | None | None | Stops all tasks in `OrderBookTracker`.
`_emit_trade_event_loop` | None | None | Attempts to retrieve trade_messages from the Queue `_order_book_trade_stream` and apply the trade onto the respective order book.

## Debugging & Testing

As part of the QA process, for each tasks(Task 1 through 3) you are **required** to include the unit test cases for the code review process to begin. Refer to [Option 1: Unit Test Cases](/developers/connectors/debug&test/#option-1-unit-test-cases) to build your unit tests.

