# Task 3. Market Connector

The primary bulk of integrating a new exchange connector is in this section. 

The role of the `Market` class can be broken down into placing and tracking orders. Although this might seem pretty straightforward, it does require a certain level of understanding and knowing the expected side-effect(s) of certain functions.

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


## Authentication

Placing and tracking of orders on the exchange normally requiring a form of authentication tied to every requests to ensure protected access/actions to the assets that users have on the respective exchanges. 

As such, it would only make sense to have a module dedicated to handling authentication.

As briefly mentioned, the `Auth` class is responsible for creating the request parameters and/or data bodies necessary to authenticate an API request.

!!! note
    Mainly used in the `Market` class, but may be required in the `UserStreamTrackerDataSource` to authenticate subscribing to a WebSocket connection in [`listen_for_user_stream`](../task2/#userstreamtrackerdatasource).

Function<div style="width:150px"/> | Input Parameter(s) | Expected Output(s)(s) | Description
---|---|---|---
`generate_auth_dict` | http_method: `str`,<br/>url: `str`,<br/>params: `Dict[str, any]`,<br/>body: `Dict[str, any]` | `Dict[str, any]` | Generates the url and the valid signature to authenticate a particular API request.

!!! tip
    The **input parameters** and **return** value(s) can be modified accordingly to suit the exchange connectors. In most cases, the above parameters are required when creating a signature.

## Market

The section below will describe in detail what is required for the `Market` class to place and track orders.

### Placing Orders
 
`execute_buy` and `execute_sell` are the crucial functions when placing orders on the exchange,. The table below will describe the task of these functions.

Function<div style="width:150px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`execute_buy` | order_id: `str`,<br/>symbol: `str`,<br/>amount: `Decimal`,<br/>order_type: `OrderType`,<br/>price: `Optional[Decimal] = s_decimal_0`| None | Function that takes the strategy inputs, auto corrects itself with trading rules, and places a buy order by calling the `place_order` function.<br/><br/>This function also begins to track the order by calling the `c_start_tracking_order` and `c_trigger_event` function.<br/>
`execute_sell` | order_id: `str`,<br/>symbol: `str`,<br/>amount: `Decimal`,<br/>order_type: `OrderType`,<br/>price: `Optional[Decimal] = s_decimal_0` | None | Function that takes the strategy inputs, auto corrects itself with trading rules, and places a sell order by calling the `place_order` function.

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
`order_type` | `OrderType`         | OrderType.LIMIT, OrderType.LIMIT_MAKER or OrderType.MARKET <br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: LIMIT_MAKER should be used as market maker and LIMIT as market taker(using price to cross the orderbook) for exchanges that support LIMIT_MAKER. Otherwise, the the usual MARKET OrderType should be used as market taker and LIMIT as market taker.</td></tr></tbody></table>
`price`      | `Optional[Decimal]` | If `order_type` is `LIMIT`, it represents the rate at which the `amount` base currency is being bought/sold at.<br/>If `order_type` is `LIMIT_MAKER`, it also represents the rate at which the `amount` base currency is being bought/sold at. However, this `OrderType` is expected to be a **post only** order(i.e should ideally be rejected by the exchange if it'll cross the market)<br/>If `order_type` is `MARKET`, this is **not** used(`price = s_decimal_0`). <br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: `s_decimal_0 = Decimal(0)` </td></tr></tbody></table>

### Cancelling Orders

The `execute_cancel` function is the primary function used to cancel any particular tracked order. Below is a quick overview of the `execute_cancel` function

Function<div style="width:150px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`execute_cancel` | symbol: `str`,<br/>order_id: `str` | order_id: `str` | Function that makes API request to cancel an active order and returns the `order_id` if it has been successfully cancelled or no longer needs to be tracked.<br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: This function also stops tracking the order by calling the `c_stop_tracking_order` and `c_trigger_event` functions. </td></tr></tbody></table>
   
### Tracking Orders & Balances

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

If the exchange doesn't provide user balance updates in real-time (web socket), you will need to set `self._real_time_balance_update = False` in the market constructor (init). 
 
And, you will need to take `in_flight_orders` snapshot during `_update_balances` as below:

```python
    self._in_flight_orders_snapshot = {k: copy.copy(v) for k, v in self._in_flight_orders.items()}
    self._in_flight_orders_snapshot_timestamp = self._current_timestamp
``` 

This is so that the connector can use default current balance calculation (in `market_base`) for available balances.
 
!!! tip
    Refer to [Order Lifecycle](../tutorial/#order-lifecycle-and-market-events) for a more detailed description on how orders are being tracked in Hummingbot.
    
    It is necessary that the above functions adhere to the flow as defined in the order lifecycle for the connector to work as intended.

### Trading Rules

Trading Rules are defined by the respective exchanges. It is crucial that Hummingbot manage and maintain the set of trading rules to ensure that there will be no issues when placing orders.

A list of some common rules can be seen in [`trading_rule.pyx`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/trading_rule.pyx).

!!! tip
    Most exchanges have a minimum trading size. Not all rules need to be defined, however, it is essential to meet the rules as specified by the exchange.
   
All trading rules are stored in `self._trading_rules` in the `Market` class.

The table below details the functions responsible for maintaining the `TradeRule` for each trading pair

Function<div style="width:150px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`_trading_rules_polling_loop` | None | None | A background process that periodically polls for trading rule changes. Since trading rules tend not to change as often as account balances and order statuses, this is done less often. This function is responsible for calling `_update_trading_rules`
`_update_trading_rules` | None | None | Gets the necessary trading rules definitions form the corresponding REST API endpoints. Calls `_format_trading_rules`; that parses and updates the `_trading_rules` variable in the `Market` class.
`_format_trading_rules` | `List[Any]` | `List[TradingRule]` | Parses the raw JSON response into a list of [`TradingRule`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/trading_rule.pyx). <table><tbody><tr><td bgcolor="#ecf3ff">**Note**: This is important since exchanges might only accept certain precisions and impose a minimum trade size on the order.</td></tr></tbody></table>

### Order Price/Size Quantum & Quantize Order Amount

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

### Additional Required Function(s)

Below are a list of `required` functions for the `Market` class to be fully functional.

Function<div style="width:150px"/> | Input Parameter(s) | Expected Output(s) | Description
---|---|---|---
`name` | `None` | `str` | Returns a lower case name / id for the market. Must stay consistent with market name in global settings.
`order_books` | `None` | `Dict[str, OrderBook` | Returns a mapping of all the order books that are being tracked. 
`*_auth` | `None` | `*Auth` | Returns the `Auth` class of the market.
`status_dict` | `None` | `Dict[str, bool]` | Returns a dictionary of relevant status checks. This is necessary to tell the Hummingbot client if the market has been initialized.
`ready` | `None` | `bool` | This function calls `status_dict` and returns a boolean value that indicates if the market has been initialized and is ready for trading. 
`limit_orders` | `None` | `List[LimitOrder]` | Returns a list of active limit orders being tracked.
`in_flight_orders` | `None` | `Dict[str, InFlightOrderBase]` | Returns a dictionary of all in flight orders. 
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

