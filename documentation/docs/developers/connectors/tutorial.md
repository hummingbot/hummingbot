# Building Connectors

!!! note "Important changes by release"
    This [page](https://www.notion.so/hummingbot/a26c8bcf30284535b0e5689d45a4fe88?v=869e73f78f0b426288476a2abda20f2c) lists all relevant updates to Hummingbot codebase aimed to help connector developers in making the requisite changes to their connectors.

## Introduction
This guide is intended to get you familiarized with basic structure of a connector in Hummingbot. It will guide you through the scope of creating/modifying the necessary components to implement a connector.

By the end of this guide, you should: 

* Have a general understanding of the base classes that serve as building blocks of a connector
* Be able to integrate new connectors from scratch

Implementing a new connector can generally be split into 3 major tasks:

1. [Data Source & Order Book Tracker](#task-1-data-source-order-book-tracker)
2. [User Stream Tracker](#task-2-user-stream-tracker)
3. [Market Connector](#task-3-market-connector)


## Task 1. Data Source & Order Book Tracker

Generally the first 2 components you should begin with when implementing your own connector are the `OrderBookTrackerDataSource` and `OrderBookTracker`.

The `OrderBookTracker` contains subsidiary classes that help maintain the real-time order book of a market. Namely, the classes are `OrderBookTrackerDataSource` and `ActiveOrderTracker`.

### OrderBookTrackerDataSource

The `OrderBookTrackerDataSource` class is responsible for making API calls and/or WebSocket queries to obtain order book snapshots, order book deltas and miscellaneous information on order book.

Integrating your own data source component would require you to extend from the `OrderBookTrackerDataSource` base class [here](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/data_type/order_book_tracker_data_source.py).

The table below details the **required** functions in `OrderBookTrackerDataSource`:

Function<div style="width:200px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`get_last_traded_prices` | trading_pairs: List[str] | `Dict[str, float]` | Performs the necessary API request(s) to get last traded price for the given markets (trading_pairs) and return a dictionary of trading_pair and last traded price.
`get_snapshot` | client: `aiohttp.ClientSession`, trading_pair: `str` | `Dict[str, any]` | Fetches order book snapshot for a particular trading pair from the exchange REST API. <table><tbody><tr><td bgcolor="#ecf3ff">**Note**: Certain exchanges do not add a timestamp/nonce to the snapshot response. In this case, to maintain a real-time order book would require generating a timestamp for every order book snapshot and delta messages received and applying them accordingly.<br/><br/>In [Bittrex](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/bittrex/bittrex_api_order_book_data_source.py), this is performed by invoking the `queryExchangeState` topic on the SignalR WebSocket client.</td></tr></tbody></table>
`get_new_order_book` | trading_pairs: `List[str]` | `OrderBook` | Create a new order book instance and populate its `bids` and `asks` by applying the order_book snapshot to the order book, you might need to involve `ActiveOrderTracker` below. 
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
    `OrderBookRow` should only be used in the `ActiveOrderTracker` class, while `ClientOrderBookRow` should only be used in the `Market` class. This is due to improve performance especially since calculations in `float` fair better than that of `Decimal`.

### OrderBookTracker

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

The `UserStreamTracker` main responsibility is to fetch user account data and queues it accordingly.

`UserStreamTracker` contains subsidiary classes that help maintain the real-time wallet/holdings balance and open orders of a user. Namely, the classes required are `UserStreamTrackerDataSource`, `UserStreamTracker` and `MarketAuth`(if applicable).

!!! note
    This is only required in **Centralized Exchanges**.

### UserStreamTrackerDataSource

The `UserStreamTrackerDataSource` class is responsible for initializing a WebSocket connection to obtain user related trade and balances updates.

Integrating your own data source component would require you to extend from the UserStreamTrackerDataSource base class here.

The table below details the **required** functions in `UserStreamTrackerDataSource`:

Function<div style="width:200px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`last_recv_time` | None | `float` | Should be updated(using python's time.time()) everytime a message is received from the websocket.	
`listen_for_user_stream` | ev_loop: `asyncio.BaseEventLoop`<br/>output: `asyncio.Queue` | None | Subscribe to user stream via web socket, and keep the connection open for incoming messages

### UserStreamTracker

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
 
### Authentication

The `Auth` class is responsible for crafting the request parameters and bodies that are necessary for certain API requests.

For a more detailed explanation and implementation details, please refer to the [Authentication](#task-3-market-connector) section in the Task 3.

## Task 3. Market Connector

The primary bulk of integrating a new exchange connector is in the section. 

The role of the `Market` class can be broken down into placing and tracking orders. Although this might seem pretty straightforward, it does require a certain level of understanding and knowing the expected side-effect(s) of certain functions.

### Authentication

Placing and tracking of orders on the exchange normally requiring a form of authentication tied to every requests to ensure protected access/actions to the assets that users have on the respective exchanges. 

As such, it would only make sense to have a module dedicated to handling authentication.

As briefly mentioned, the `Auth` class is responsible for creating the request parameters and/or data bodies necessary to authenticate an API request.

!!! note
    Mainly used in the `Market` class, but may be required in the `UserStreamTrackerDataSource` to authenticate subscribing to a WebSocket connection in [`listen_for_user_stream`](#userstreamtrackerdatasource).

Function<div style="width:150px"/> | Input Parameter(s) | Expected Output(s)(s) | Description
---|---|---|---
`generate_auth_dict` | http_method: `str`,<br/>url: `str`,<br/>params: `Dict[str, any]`,<br/>body: `Dict[str, any]` | `Dict[str, any]` | Generates the url and the valid signature to authenticate a particular API request.

!!! tip
    The **input parameters** and **return** value(s) can be modified accordingly to suit the exchange connectors. In most cases, the above parameters are required when creating a signature.

### Market

The section below will describe in detail what is required for the `Market` class to place and track orders.

#### Placing Orders
 
`execute_buy` and `execute_sell` are the crucial functions when placing orders on the exchange,. The table below will describe the task of these functions.

Function<div style="width:150px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`execute_buy` | order_id: `str`,<br/>symbol: `str`,<br/>amount: `Decimal`,<br/>order_type: `OrderType`,<br/>price: `Optional[Decimal] = s_decimal_0`| None | Function that takes the strategy inputs, auto corrects itself with trading rules, and places a buy order by calling the `place_order` function.<br/><br/>This function also begins to track the order by calling the `c_start_tracking_order` and `c_trigger_event` function.<br/>
`execute_buy` | order_id: `str`,<br/>symbol: `str`,<br/>amount: `Decimal`,<br/>order_type: `OrderType`,<br/>price: `Optional[Decimal] = s_decimal_0` | None | Function that takes the strategy inputs, auto corrects itself with trading rules, and places a buy order by calling the `place_order` function.

!!! tip
    The `execute_buy` and `execute_sell` methods verify that the trades would be allowed given the trading rules obtained from the exchange and calculate applicable trading fees. They then must do the following:
    
    - Quantize the order amount to ensure that the precision is as required by the exchange
    - Create a `params` dictionary with the necessary parameters for the desired order
    - Pass the `params` to an `Auth` object to generate the signature and place the order
    - Pass the resulting order ID and status along with the details of the order to an `InFlightOrder`
    
    `InFlightOrders` are stored within a list in the `Market` class, and are Hummingbot’s internal records of orders it has placed that remain open on the market. When such orders are either filled or canceled, they are removed from the list and the relevant event completion flag is passed to the strategy module.

Considering that placing of orders normally involves a `POST` request to a particular buy/sell order REST API endpoint. This would **require** additional parameters like :

Variable(s)<div style="width:100px"/>  | Type                | Description
-------------|---------------------|-------------
`order_id`   | `str`               | A generated, client-side order ID that will be used to identify an order by the Hummingbot client.<br/> The `order_id` is generated in the `c_buy` function.
`symbol`     | `str`               | The trading pair string representing the market on which the order should be placed. i.e. (ZRX-ETH) <br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: Some exchanges have the trading pair symbol in `Quote-Base` format. Hummingbot requires that all trading pairs to be in `Base-Quote` format.</td></tr></tbody></table>
`amount`     | `Decimal`           | The total value, in base currency, to buy/sell.
`order_type` | `OrderType`         | OrderType.LIMIT, OrderType.LIMIT_MAKER or OrderType.MARKET <br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: LIMIT_MAKER should be used as market maker and LIMIT as market taker(using price to cross the orderbook) for exchanges that support LIMIT_MAKER. Otherwise, the the usual MARKET OrderType should be used as market taker and LIMIT as market taker.
`price`      | `Optional[Decimal]` | If `order_type` is `LIMIT`, it represents the rate at which the `amount` base currency is being bought/sold at.<br/>If `order_type` is `LIMIT_MAKER`, it also represents the rate at which the `amount` base currency is being bought/sold at. However, this `OrderType` is expected to be a **post only** order(i.e should ideally be rejected by the exchange if it'll cross the market)<br/>If `order_type` is `MARKET`, this is **not** used(`price = s_decimal_0`). <br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: `s_decimal_0 = Decimal(0)` </td></tr></tbody></table>

#### Cancelling Orders

The `execute_cancel` function is the primary function used to cancel any particular tracked order. Below is a quick overview of the `execute_cancel` function

Function<div style="width:150px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`execute_cancel` | symbol: `str`,<br/>order_id: `str` | order_id: `str` | Function that makes API request to cancel an active order and returns the `order_id` if it has been successfully cancelled or no longer needs to be tracked.<br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: This function also stops tracking the order by calling the `c_stop_tracking_order` and `c_trigger_event` functions. </td></tr></tbody></table>
   
#### Tracking Orders & Balances

The `Market` class tracks orders in several ways:

- Listening on user stream<br/>
This is primarily done in the `_user_stream_event_listener` function. This is only done when the exchange has a WebSocket API.

- Periodic status polling<br/>
This serves as a fallback for when user stream messages are not caught by the `UserStreamTracker`. This is done by the `_status_polling_loop` 

The table below details the **required** functions to implement

Function<div style="width:150px"/> | Description
---|---
`_user_stream_event_listener`| Update order statuses and/or account balances from incoming messages from the user stream.
`_update_balances`| Pulls the REST API for the latest account balances and updates `_account_balances` and `_account_available_balances`.
`_update_order_status`| Pulls the REST API for the latest order statuses and updates the order statuses of locally tracked orders.


!!! tip
    Refer to [Order Lifecycle](/developers/connectors/order-lifecycle) for a more detailed description on how orders are being tracked in Hummingbot.
    
    It is necessary that the above functions adhere to the flow as defined in the order lifecycle for the connector to work as intended.

#### Trading Rules

Trading Rules are defined by the respective exchanges. It is crucial that Hummingbot manage and maintain the set of trading rules to ensure that there will be no issues when placing orders.

A list of some common rules can be seen in [`trading_rule.pyx`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/trading_rule.pyx).

!!! tip
    Most exchanges have a minimum trading size. Not all rules need to be defined, however, it is essential to meet the rules as specified by the exchange.
   
All trading rules are stored in `self._trading_rules` in the `Market` class.

The table below details the functions responsible for maintaining the `TradeRule` for each trading pair

Function<div style="width:150px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`_trading_rules_polling_loop` | None | None | A background process that periodically polls for trading rule changes. Since trading rules tend not to change as often as account balances and order statuses, this is done less often. THis function is responsible for calling `_update_trading_rules`
`_update_trading_rules` | None | None | Gets the necessary trading rules definitions form the corresponding REST API endpoints. Calls `_format_trading_rules`; that parses and updates the `_trading_rules` variable in the `Market` class.
`_format_trading_rules` | `List[Any]` | `List[TradingRule]` | Parses the raw JSON response into a list of [`TradingRule`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/trading_rule.pyx). <table><tbody><tr><td bgcolor="#ecf3ff">**Note**: This is important since exchanges might only accept certain precisions and impose a minimum trade size on the order.</td></tr></tbody></table>

#### Order Price/Size Quantum & Quantize Order Amount

This, together with the trading rules, ensure that all orders placed by Hummingbot meet the required specifications as defined by the exchange.

!!! note
    These checks are performed in `execute_buy` and `execute_sell` **before** placing an order.<br/>
    In the event where the orders proposed by the strategies fail to meet the requirements as defined in the trading rules, the intended behaviour for the `Market` class is simply to raise an error and not place the order.<br/>
    You may be required to add additional functions to help determine if an order meets the necessary requirements.

The table below details some functions responsible for this.

Function<div style="width:150px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`c_get_order_price_quantum` | `str trading_pair`,<br/>`object price` | `Decimal` | Gets the minimum increment interval for an order price.
`c_get_order_size_quantum` | `str trading_pair`,<br/>`object order_size` | `Decimal` | Gets the minimum increment interval for an order size (i.e. 0.01 .USD)
`c_quantize_order_amount` | `str trading_pair`,<br/>`object amount`,<br/>`object price=s_decimal_0`| `Decimal` | Checks the current order amount against the trading rules, and corrects(i.e simple rounding) any rule violations. Returns a valid order amount in `Decimal` format.
`c_quantize_order_price` | `str trading_pair`,<br/>`object price`,,br/>`object price=s_decimal_0`| `Decimal` | Checks the current order price against the trading rules, and corrects(i.e. simple rounding) any rule violations. Returns a valid order price in `Decimal` format.    

#### Additional Required Function(s)

Below are a list of `required` functions for the `Market` class to be fully functional.

Function<div style="width:150px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`name` | `None` | `str` | Returns a lower case name / id for the market. Must stay consistent with market name in global settings.
`order_books` | `None` | `Dict[str, OrderBook` | Returns a mapping of all the order books that are being tracked. 
`*_auth` | `None` | `*Auth` | Returns the `Auth` class of the market.
`status_dict` | `None` | `Dict[str, bool]` | Returns a dictionary of relevant status checks. This is necessary to tell the Hummingbot client if the market has been initialized.
`ready` | `None` | `bool` | This function calls `status_dict` and returns a boolean value that indicates if the market has been initialized and is ready for trading. 
`limit_orders` | `None` | `List[LimitOrder]` | Returns a list of active limit orders being tracked.
`tracking_states` | `None` | `Dict[str, any]` | Returns a mapping of tracked client order IDs to the respective `InFlightOrder`. Used by the `MarketsRecorder` class to orchestrate market classes at a high level.
`restore_tracking_states` | `None` | `None` | Updates InFlight order statuses from API results. This is used by the `MarketRecorder` class to orchestrate market classes at a higher level.
`start_network` | `None` | `None` | An asynchronous wrapper function used by `NetworkBase` class to handle when a single market goes online.
`stop_network` | `None` | `None` | An asynchronous wrapper function for `_stop_network`. Used by `NetworkBase` class to handle when a single market goes offline.
`check_network` | `None` | `NetworkStatus` | `An asynchronous function used by `NetworkBase` class to check if the market is online/offline.
`get_order` | `client_order_id:str`| `Dict[str, Any]` | Gets status update for a particular order via rest API.<br/><br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: You are required to retrieve the exchange order ID for the specified `client_order_id`. You can do this by calling the `get_exchange_order_id` function available in the `InFlightOrderBase`.</td></tr></tbody></table>
`supported_order_types` | `None` | `List[OrderType]` | Returns a list of OrderType(s) supported by the exchange. Examples are: `OrderType.LIMIT`, `OrderType.LIMIT_MAKER` and `OrderType.MARKET`.
`place_order` | `order_id:str`<br/>`symbol:str`<br/>`amount:Decimal`<br/>`is_buy:bool`<br/>`order_type:OrderType`<br/>`price:Decimal`| `Dict[str, Any]` | An asynchronous wrapper for placing orders through the REST API. Returns a JSON response from the API.
`cancel_all` | `timeout_seconds:float`| `List[CancellationResult]` | An asynchronous function that cancels all active orders. Used by Hummingbot's top level "stop" and "exit" commands(cancelling outstanding orders on exit). Returns a `List` of [`CancellationResult`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/data_type/cancellation_result.py).<br/><br/>A `CancellationResult` is an object that indicates if an order has been successfully cancelled with a boolean variable.
`_stop_network` | `None` | `None` | Synchronous function that handles when a single market goes offline
`_http_client` | `None` | `aiohttp.ClientSession` | Returns a shared HTTP client session instance. <table><tbody><tr><td bgcolor="#ecf3ff">**Note**: This prevents the need to establish a new session on every API request.</td></tr></tbody></table>
`_api_request` | `http_method:str`<br/>`path_url:str`<br/>`url:str`<br/>`data:Optional[Dict[str,Any]]`| `Dict[str, Any]` | An asynchronous wrapper function for submitting API requests to the respective exchanges. Returns the JSON response form the endpoints. Handles any initial HTTP status error codes. 
`_update_balances` | `None` | `None` | Gets account balance updates from the corresponding REST API endpoints and updates `_account_available_balances` and `_account_balances` class variables in the `MarketBase` class.
`_status_polling_loop` | `None` | `None` | A background process that periodically polls for any updates on the REST API. This is responsible for calling `_update_balances` and `_update_order_status`.
`c_start` | `Clock clock`<br/>`double timestamp`| `None` | A function used by the top level Clock to orchestrate components of Hummingbot.
`c_tick` | `double timestamp` | `None` | Used by top level Clock to orchestrate components of Hummingbot. This function is called frequently with every clock tick.
`c_buy` | `str symbol`,<br/>`object amount`,<br/>`object order_type=OrderType.MARKET`,<br/>`object price=s_decimal_0`,<br/>`dict kwargs={}`| `str` | A synchronous wrapper function that generates a client-side order ID and schedules a **buy** order. It calls the `execute_buy` function and returns the client-side order ID.
`c_sell` | `str symbol`,<br/>`object amount`,<br/>`object order_type=OrderType.MARKET`,<br/>`object price=s_decimal_0`,<br/>`dict kwargs={}`| `str` | A synchronous wrapper function that generates a client-side order ID and schedules a **sell** order. It calls the `execute_buy` function and returns the client-side order ID.
`c_cancel` | `str symbol`,<br/>`str order_id` | `str` | A synchronous wrapper function that schedules an order cancellation. <table><tbody><tr><td bgcolor="#ecf3ff">**Note**: The `order_id` here refers to the client-side order ID as tracked by Hummingbot.</td></tr></tbody></table>
`c_did_timeout_tx` | `str tracking_id` | `None` | Triggers `MarketEvent.TransactionFailure` when an Ethereum transaction has timed out.
`c_get_fee` | `str base_currency`,<br/>`str quote_currency`,<br/>`object order_type`,<br/>`object order_side`,<br/>`object amount`,<br/>`object price` | `TradeFee` | A function that calculates the fees for a particular order. Use `estimate_fee` module to get the fee. Returns a [`TradeFee`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py) object.
`c_get_order_book` | `str symbol` | `OrderBook` | Returns the `OrderBook` for a specific trading pair(symbol).
`c_start_tracking_order` | `str client_order_id`,<br/>`str symbol`,<br/>`object order_type`,<br/>`object trade_type`,<br/>`object price`,<br/>`object amount` | `None` | Adds a new order to the `_in_flight_orders` class variable. This essentially begins tracking the order on the Hummingbot client. 
`c_stop_tracking_order` | `str order_id` | `None` | Deletes an order from `_in_flight_orders` class variable. This essentially stops the Hummingbot client from tracking an order.


## Task 4. Hummingbot Client

This section will define the necessary files that need to be modified to allow users configure Hummingbot to use the new exchange connector.

Below are the files and the respective changes that **require** to be modified.

- `conf/__init_.py`
```python
new_market_api_key = os.getenv("NEW_MARKET_API_KEY")
new_market_secret_key = os.getenv("NEW_MARKET_SECRET_KEY")
```

- `hummingbot/client/config/global_config_map.py`
```python
"new_market_api_key": ConfigVar(key="new_market_api_key",
                             prompt="Enter your NewMarket API key >>> ",
                             required_if=using_exchange("new_market"),
                             is_secure=True),
"new_market_secret_key": ConfigVar(key="new_market_secret_key",
                                prompt="Enter your NewMarket secret key >>> ",
                                required_if=using_exchange("new_market"),
                                is_secure=True),
```

- `hummingbot/client/config/fee_overrides_config_map.py`
```python
fee_overrides_config_map = {
    "binance_maker_fee": new_fee_config_var("binance_maker_fee"),
    "binance_taker_fee": new_fee_config_var("binance_taker_fee"),
    .
    .
    .
    "new_exchange_maker_fee": new_fee_config_var("new_exchange_maker_fee"),
    "new_exchange_taker_fee": new_fee_config_var("new_exchange_taker_fee"),
```

- `hummingbot/client/hummingbot_application.py`
```python
MARKET_CLASSES = {
    .
    .
    .
    "new_market": NewMarket
}
.
.
.
  def _initialize_markets(self, market_names: List[Tuple[str, List[str]]]):
    ...
    ...
       ...
       elif market_name == "new_market":
         new_market_api_key = global_config_map.get("new_market_api_key").value
         new_market_secret_key = global_config_map.get("new_market_secret_key").value
         new_market_passphrase = global_config_map.get("new_market_passphrase").value

         market = NewMarket(new_market_api_key,
                            new_market_secret_key,
                            new_market_passphrase,
                            symbols=symbols,
                            trading_required=self._trading_required)
```

- `hummingbot/client/settings.py`
```python
EXCHANGES = {
    "bamboo_relay",
    .
    .
    .
    "new_market",
}	}

DEXES = {
    "bamboo_relay",
    .
    .
    .
    "new_market", # if it is a DEX
}

EXAMPLE_PAIRS = {
    "binance": "ZRXETH",
    .
    .
    .
    "new_market": "EXAMPLE_PAIR",
}

EXAMPLE_ASSETS = {
    "binance": "ZRX",
    .
    .
    .
    "new_market": "EXAMPLE_ASSET",
}
```
- `hummingbot/client/command/connect_command.py`
```python
OPTIONS = {
    "binance",
    .
    .
    .
    "new_exchange"
}
```

- `hummingbot/user/user_balances.py`
```python
    @staticmethod
    def connect_market(exchange, *api_details):
        market = None
        if exchange == "binance":
            market = BinanceMarket(api_details[0], api_details[1])
        .
        .
        .
        elif exchange == "new_exchange":
            market = NewExchangeMarket(api_details[0], api_details[1])
        return market
```

- `hummingbot/core/utils/trading_pair_fetcher.py`
```python
@staticmethod
async def fetch_new_market_trading_pairs() -> List[str]:
    # Returns a List of str, representing each active trading pair on the exchange.
    async with aiohttp.ClientSession() as client:
            async with client.get(NEW_MARKET_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    try:
                        all_trading_pairs: List[Dict[str, any]] = await response.json()
                        return [item["symbol"]
                                for item in all_trading_pairs
                                if item["status"] == "ONLINE"]  # Only returns active trading pairs
                    except Exception:
                        pass
                        # Do nothing if the request fails -- there will be no autocomplete available
                return []
.
.
.

async def fetch_all(self):
    binance_trading_pairs = await self.fetch_binance_trading_pairs()
    .
    .
    .
    new_market_trading_pairs = await self.fetch_new_market_trading_pairs()
    self.trading_pairs = {}
        "binance": binance_trading_pairs,
        .
        .
        .
        "new_market": new_market_trading_pairs,
```
- `hummingbot/core/utils/market_mid_price.py`
```python
def get_mid_price(exchange: str, trading_pair: str) -> Optional[Decimal]:
    .
    .
    elif exchange == "new_exchange":
        return new_exchange_mid_price(trading_pair)
        
@cachetools.func.ttl_cache(ttl=10)
def new_exchange_mid_price(trading_pair: str) -> Optional[Decimal]:
    resp = requests.get(url=...)
    records = resp.json()
    result = None
    for record in records:
        pair = new_exchange.convert_from_exchange_trading_pair(record["symbol"])
        .
        .
        .
    return result
```
- `hummingbot/core/utils/estimate_fee.py`
```python
default_cex_estimate = {
        .
        .
        "new_exchange": [maker_fee, taker_fee],
        
```
## Additional: Debugging & Testing

This section will breakdown some of the ways to debug and test the code. You are not entirely required to use the options during your development process.

!!! warning
    As part of the QA process, for each tasks(Task 1 through 3) you are **required** to include the unit test cases for the code review process to begin. Refer to [Option 1: Unit Test Cases](#option-3-unit-test-cases) to build your unit tests.
    
### Option 1. Unit Test Cases

For each tasks(1->3), you are required to create a unit test case. Namely they are `test_*_order_book_tracker.py`, `test_*_user_stream_tracker.py` and `test_*_market.py`. 
Examples can be found in the [test/integration](https://github.com/CoinAlpha/hummingbot/tree/master/test/integration) folder.

Below are a list of items required for the Unit Tests:

1. Data Source & Order Tracker | `test_*_order_book_tracker.py`<br/>
The purpose of this test is to ensure that the `OrderBookTrackerDataSource` and `OrderBookTracker` and all its functions are working as intended.
Another way to test its functionality is using a Debugger to ensure that the contents `OrderBook` mirrors that on the exchange.

2. User Stream Tracker | `test_*_user_stream_tracker.py`<br/>
The purpose of this test is to ensure that the `UserStreamTrackerDataSource` and `UserStreamTracker` components are working as intended.
This only applies to exchanges that has a WebSocket API. As seen in the examples for this test, it simply outputs all the user stream messages. 
It is still required that certain actions(buy and cancelling orders) be performed for the tracker to capture. Manual message comparison would be required.

    i.e. Placing a single LIMIT-BUY order on Bittrex Exchange should return the following(some details are omitted)

    ```Bash tab="Order Detail(s)"
    Trading Pair: ZRX-ETH
    Order Type: LIMIT-BUY
    Amount: 100ZRX
    Price: 0.00160699ETH
    ```
    
    ```Bash tab="Action(s) Performed"
    1. Placed LIMIT BUY order.
    2. Cancel order.
    ```
    
    ```Bash tab="Expected output"
    # Below is the outcome of the test. Determining if this is accurate would still be necessaru.
    
    <Queue maxsize=0 _queue=[
        BittrexOrderBookMessage(
            type=<OrderBookMessageType.DIFF: 2>, 
            content={
                'event_type': 'uB',
                'content': {
                    'N': 4,
                    'd': {
                        'U': '****', 
                        'W': 3819907,
                        'c': 'ETH',
                        'b': 1.13183357, 
                        'a': 0.96192245, 
                        'z': 0.0,
                        'p': '0x****',
                        'r': False, 
                        'u': 1572909608900,
                        'h': None
                    }
                }, 
                'error': None, 
                'time': '2019-11-04T23:20:08'
            },
            timestamp=1572909608.0
        ), 
        BittrexOrderBookMessage(
            type=<OrderBookMessageType.DIFF: 2>,
            content={
                'event_type': 'uO',
                'content': {
                    'w': '****',
                    'N': 44975,
                    'TY': 0,
                    'o': {
                        'U': '****',
                        'I': 3191361360,
                        'OU': '****',
                        'E': 'XRP-ETH',
                        'OT': 'LIMIT_BUY',
                        'Q': 100.0,
                        'q': 100.0,
                        'X': 0.00160699,
                        'n': 0.0,
                        'P': 0.0,
                        'PU': 0.0,
                        'Y': 1572909608900,
                        'C': None,
                        'i': True,
                        'CI': False,
                        'K': False,
                        'k': False,
                        'J': None,
                        'j': None,
                        'u': 1572909608900,
                        'PassthroughUuid': None
                    }
                },
                'error': None,
                'time': '2019-11-04T23:20:08'
            }, 
            timestamp=1572909608.0
        ),
        BittrexOrderBookMessage(
            type=<OrderBookMessageType.DIFF: 2>,
            content={
                'event_type': 'uB',
                'content': {
                    'N': 5,
                    'd': {
                        'U': '****',
                        'W': 3819907,
                        'c': 'ETH', 
                        'b': 1.13183357, 
                        'a': 1.1230232,
                        'z': 0.0,
                        'p': '****',
                        'r': False,
                        'u': 1572909611750,
                        'h': None
                    }
                }, 
                'error': None, 
                'time': '2019-11-04T23:20:11'
            }, 
            timestamp=1572909611.0
        ), 
        BittrexOrderBookMessage(
            type=<OrderBookMessageType.DIFF: 2>,
            content={
                'event_type': 'uO',
                'content': {
                    'w': '****',
                    'N': 44976, 
                    'TY': 3, 
                    'o': {
                        'U': '****', 
                        'I': 3191361360, 
                        'OU': '****', 
                        'E': 'XRP-ETH', 
                        'OT': 'LIMIT_BUY', 
                        'Q': 100.0, 
                        'q': 100.0, 
                        'X': 0.00160699, 
                        'n': 0.0, 
                        'P': 0.0, 
                        'PU': 0.0, 
                        'Y': 1572909608900, 
                        'C': 1572909611750, 
                        'i': False, 
                        'CI': True,
                        'K': False,
                        'k': False, 
                        'J': None, 
                        'j': None, 
                        'u': 1572909611750, 
                        'PassthroughUuid': None
                    }
                }, 
                'error': None, 
                'time': '2019-11-04T23:20:11'
            }, 
            timestamp=1572909611.0
        )
    ] tasks=4>
    ```

3. Market Connector | `test_*_market.py`<br/>
The purpose of this test is to ensure that all components and the order life cycle is working as intended. 
This test determines if the connector is able to place and manage orders.<br/>
All the tests below are required to pass successfully on both real API calls and mocked API calls modes.<br/>
The mocked API calls mode is to facilitate testing where we can run tests as often as we want without incurring costs in 
transactions and slippage.<br/>
In the mocked mode, we simulate any API calls where exchange API key and secret are required,
i.e. in this mode all the tests should pass without using real exchange API credentials.<br/><br/>
To simulate REST API responses, please use `test.integration.humming_web_app.HummingWebApp`, key steps to follow are as below:
  - Create environment variables<br/>  
  `MOCK_API_ENABLED` - true or false - to indicate whether to run the tests in mocked API calls mode<br/>
  `NEW_EXCHAGE_API_KEY` - string - the exchange API key<br/>
  `NEW_EXCHAGE_API_SECRET` - string - the exchange API secret<br/>
  In your `test_*_market.py` 
  ```python
  import conf
  .
  .
  .
  API_MOCK_ENABLED = conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
  API_KEY = "XXX" if API_MOCK_ENABLED else conf.binance_api_key
  API_SECRET = "YYY" if API_MOCK_ENABLED else conf.binance_api_secret
  ```

  - Start HummingWebApp<br/>
  Configure the web app on what url host to mock and which url paths to ignore, then start the web app. 
  ```python
  @classmethod
  def setUpClass(cls):
      cls.ev_loop = asyncio.get_event_loop()
      if API_MOCK_ENABLED:
          cls.web_app = HummingWebApp.get_instance()
          cls.web_app.add_host_to_mock(API_HOST, ["/products", "/currencies"])
          cls.web_app.start()
          cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())
   ```

  - Patch http requests<br/>
  If you use `requests` library:
  ```python
  cls._req_patcher = mock.patch.object(requests.Session, "request", autospec=True)
  cls._req_url_mock = cls._req_patcher.start()
  cls._req_url_mock.side_effect = HummingWebApp.reroute_request
  ```
  If you use `aiohttp` library:
  ```python
  cls._patcher = mock.patch("aiohttp.client.URL")
  cls._url_mock = cls._patcher.start()
  cls._url_mock.side_effect = cls.web_app.reroute_local
  ```
  
  - Preset json responses<br/>
  Use `update_response` to store the mocked response to the endpoint which you want to mock, e.g.
  ```python
  cls.web_app.update_response("get", cls.base_api_url, "/api/v3/account", FixtureBinance.GET_ACCOUNT)
  ```
  Please store your mocked json response in `test/integration/assets/mock_data/fixture_new_exchange.py`
  e.g. 
  ```python
  class FixtureBinance:
  GET_ACCOUNT = {"makerCommission": 10, "takerCommission": 10, "buyerCommission": 0, "sellerCommission": 0,
                   "canTrade": True, "canWithdraw": True, "canDeposit": True, "updateTime": 1580009996654,
                   "accountType": "SPOT", "balances": [{"asset": "BTC", "free": "0.00000000", "locked": "0.00000000"},
                                                       {"asset": "ETH", "free": "0.77377698", "locked": "0.00000000"},
                                                       {"asset": "LINK", "free": "4.99700000", "locked": "0.00000000"}]}
  ```
  Please remove any sensitive information from this file, e.g. your account number, keys, secrets,...<br/> 
  
To simulate web socket API responses, please use `test.integration.humming_ws_server.HummingWsServerFactory`.<br/> 
Key steps to follow are as below:<br/>
  - Start new server for each web socket connection<br/>
  ```python
  @classmethod
  def setUpClass(cls):
      cls.ev_loop = asyncio.get_event_loop()
      if API_MOCK_ENABLED:
          ws_base_url = "wss://stream.binance.com:9443/ws"
          cls._ws_user_url = f"{ws_base_url}/{FixtureBinance.GET_LISTEN_KEY['listenKey']}"
          HummingWsServerFactory.start_new_server(cls._ws_user_url)
          HummingWsServerFactory.start_new_server(f"{ws_base_url}/linketh@depth/zrxeth@depth")
   ```

  - Patch `websockets`<br/>
  ```python
  cls._ws_patcher = unittest.mock.patch("websockets.connect", autospec=True)
  cls._ws_mock = cls._ws_patcher.start()
  cls._ws_mock.side_effect = HummingWsServerFactory.reroute_ws_connect
  ```
  
  - Send json responses<br/>
  In the code where you are expecting json response from the server. 
  ```python
  HummingWsServerFactory.send_json_threadsafe(self._ws_user_url, data1, delay=0.1)
  HummingWsServerFactory.send_json_threadsafe(self._ws_user_url, data2, delay=0.11)
  ```
  `data` is your fixture data.<br/>
  Make sure to set some delay if sequence of responses matters, in the above example, data2 is supposed to arrive after data1

In cases where you need to preset `client_order_id` (our internal id), please mock it as below:<br/>
- Patch `get_tracking_nonce`
  ```python
  cls._t_nonce_patcher = unittest.mock.patch("hummingbot.market.binance.binance_market.get_tracking_nonce")
  cls._t_nonce_mock = cls._t_nonce_patcher.start()
  ```

- Mock the nonce and create order_id as required
  ```python
  self._t_nonce_mock.return_value = 10001
  order_id = f"{side.lower()}-{trading_pair}-{str(nonce)}"
  ```

Finally, stop all patchers and the web app.<br/>
Once all tests are done, stop all these services.<br/>
```python
@classmethod
def tearDownClass(cls) -> None:
  if API_MOCK_ENABLED:
      cls.web_app.stop()
      cls._patcher.stop()
      cls._req_patcher.stop()
      cls._ws_patcher.stop()
      cls._t_nonce_patcher.stop()
```
<br/>
Below are a list of tests that are **required**:

Function<div style="width:200px"/> | Description 
---|---
`test_get_fee` | Tests the `get_fee` function in the `Market` class. Ensures that calculation of fees are accurate.
`test_limit_buy` | Utilizes the `place_order` function in the `Market` class and tests if the market connector is capable of placing a LIMIT buy order on the respective exchange. Asserts that a `BuyOrderCompletedEvent` and `OrderFilledEvent`(s) have been captured.<br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: Important to ensure that the amount specified in the order has been completely filled.</td></tr></tbody></table>
`test_limit_sell` | Utilizes the `place_order` function in the `Market` class and tests if the market connector is capable of placing a LIMIT sell order on the respective exchange.
`test_limit_maker_rejections` | Utilizes the `place_order` function in the `Market` class and tests that the exchage rejects LIMIT_MAKER orders when the prices of such orders cross the orderbook.
`test_limit_makers_unfilled` | Utilizes the `place_order` function in the `Market` class to successfully place buy and sell LIMIT_MAKER orders and tests that they are unfilled after they've been placed in the orderbook.
`test_market_buy` | Utilizes the `place_order` function in the `Market` class and tests if the market connector is capable of placing a MARKET buy order on the respective exchange.
`test_market_sell` | Utilizes the `place_order` function in the `Market` class and tests if the market connector is capable of placing a MARKET sell order on the respective exchange.
`test_cancel_order` | Utilizes the `cancel_order` function in the `Market` class and tests if the market connector is capable of cancelling an order. <table><tbody><tr><td bgcolor="#ecf3ff">**Note**: Ensures that the Hummingbot client is capable of resolving the `client_order_id` to obtain the `exchange_order_id` before posting the cancel order request. </td></tr></tbody></table>
`test_cancel_all` | Tests the `cancel_all` function in the `Market` class. All orders(being tracked by Hummingbot) would be cancelled.
`test_list_orders` | Places an order before checking calling the `list_orders` function in the `Market` class. Checks the number of orders and the details of the order. 
`test_order_saving_and_restoration` | Tests if **tracked orders** are being recorded locally and determines if the Hummingbot client is able to restore the orders.
`test_order_fill_record` | Tests if **trades** are being recorded locally.
`test_get_wallet_balances` (DEXes only) | Tests the `get_all_balances` function in the `Market` class.<br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: This is only required in Decentralized Exchanges.</td></tr></tbody></table>
`test_wrap_eth` (DEXes only) | Tests the `wrap_eth` function in the `Wallet` class. <br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: This is only required in Decentralized Exchanges that support WETH wrapping and unwrapping.</td></tr></tbody></table>
`test_unwrap_eth` (DEXes only)| Tests the `unwrap_eth` function in the `Wallet class.<br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: This is only required in Decentralized Exchanges that support WETH wrapping and unwrapping.</td></tr></tbody></table>

!!! note
    Ensure that you have enough asset balance before testing. Also document the **minimum** and **recommended** asset balance to run the tests. This is to aid testing during the PR review process.<br/>
Please see `test/integration/test_binance_market.py` as an example on how this task is done.

### Option 2. aiopython console
This option is mainly used to test for specific functions. Considering that many of the functions are asynchronous functions, 
it would be easier to test for these in the aiopython console. Click [here](https://aioconsole.readthedocs.io/en/latest/) for some documentation on how to use aiopython.

Writing short code snippets to examine API responses and/or how certain functions in the code base work would help you understand the expected side-effects of these functions and the overall logic of the Hummingbot client. 


#### Issue a API Request
Below is just a short example on how to write a short asynchronous function to mimic a API request to place an order and displaying the response received.


```python3
# Prints the response of a sample LIMIT-BUY Order
# Replace the URL and params accordingly.

>>> import aiohttp
>>> URL="api.test.com/buyOrder"
>>> params = {
...     "symbol": "ZRXETH",
...     "amount": "1000",
...     "price": "0.001",
...     "order_type": "LIMIT"
... }
>>> async with aiohttp.ClientSession() as client:
...    async with client.request("POST",
...                              url=URL,
...                              params=params) as response:
...        if response == 200:
...            print(await response.json())

```

#### Calling a Class Method
i.e. Printing the output from `get_active_exchange_markets()` function in `OrderBookTrackerDataSource`.

```python3
# In this example, we will be using BittrexAPIOrderBookDataSource

>>> from hummingbot.market.bittrex.BittrexAPIOrderBookDataSource import BittrexAPIOrderBookDataSource as b
>>> await b.get_active_exchange_markets() 

                 askRate baseAsset        baseVolume  ...             volume     USDVolume old_symbol
symbol                                                ...
BTC-USD    9357.49900000       BTC  2347519.11072768  ...       251.26097386  2.351174e+06    USD-BTC
XRP-BTC       0.00003330       XRP       83.81218622  ...   2563786.10102864  7.976883e+05    BTC-XRP
BTC-USDT   9346.88236735       BTC   538306.04864142  ...        57.59973765  5.379616e+05   USDT-BTC
.
.
.
[339 rows x 18 columns]
```

### Option 3. Custom Scripts
This option, like in Option 2, is mainly used to test specific functions. This is mainly useful when debugging how various functions/classes interact with one another.

i.e. Initializing a simple websocket connection to listen and output all captured messages to examine the user stream message when placing/cancelling an order. 
This is helpful when determining the exact response fields to use.

i.e. A simple function to craft the Authentication signature of a request. This together with [POSTMAN](https://www.getpostman.com/) can be used to check if you are generating the appropriate authentication signature for the respective requests.

#### API Request: POST Order

Below is a sample code for POST-ing a LIMIT-BUY order on Bittrex. This script not only tests the `BittrexAuth` class but also outputs the response from the API server. 

```python
#!/usr/bin/env python3

import asyncio
import aiohttp
from typing import Dict
from hummingbot.market.bittrex.bittrex_auth import BittrexAuth

BITTREX_API_ENDPOINT = "https://api.bittrex.com/v3"

async def _api_request(http_method: str,
                       path_url: str = None,
                       params: Dict[str, any] = None,
                       body: Dict[str, any] = None,
                       ):
    url = f"{BITTREX_API_ENDPOINT}{path_url}"

    auth = BittrexAuth(
        "****",
        "****"
    )

    auth_dict = auth.generate_auth_dict(http_method, url, params, body, '')

    headers = auth_dict["headers"]

    if body:
        body = auth_dict["body"]

    client = aiohttp.ClientSession()

    async with client.request(http_method,
                              url=url,
                              headers=headers,
                              params=params,
                              data=body) as response:
        data: Dict[str, any] = await response.json()
        if response.status not in [200,201]:
            print(f"Error occurred. HTTP Status {response.status}: {data}")
        print(data)

# POST order
path_url = "/orders"

body = {
    "marketSymbol": "FXC-BTC",
    "direction": "BUY",
    "type": "LIMIT",
    "quantity": "1800",
    "limit": "3.17E-7",  # Note: This will throw an error
    "timeInForce": "GOOD_TIL_CANCELLED"
}

loop = asyncio.get_event_loop()
loop.run_until_complete(_api_request("POST",path_url=path_url,body=body))
loop.close()


```

## Examples / Templates

Please refer to [Examples / Templates](/developers/connectors/#examples-templates) for some existing reference when implementing a connector.


