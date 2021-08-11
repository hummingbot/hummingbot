# Task 3 — Exchange Connector & InFlightOrder

## Overview

In Task 3, we will be required to implement both `InFlightOrder` and `Exchange` Class. This is because the primary bulk of implementing a new exchange connector is in this task.

### InFlightOrder Class

As seen in the [Exchange Component Overview](architecture/#exchange-component-overview), the `Exchange` class depends on the `InFlightOrder` Class.
The `InFlightOrder` abstracts an order's details and is primarily used by the `Exchange` class to manage all active orders.

The **_InFlightOrder Class Diagram_**, given below, details the critical variables and functions in the `InFlightOrder` class.

![InFlightOrderUMLDiagram](/assets/img/in-flight-order-class-diagram.svg)

Below are the functions that need to be implemented in the new `InFlightOrder` class.

| Function(s)                | Input                          | Output          | Description                                                                                                             |
| -------------------------- | ------------------------------ | --------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `is_done`                  | `None`                         | `bool`          | Returns `True` if the order state is completely filled or cancelled.                                                    |
| `is_failure`               | `None`                         | `bool`          | Returns `True` if placing the order is unsuccesfully.                                                                   |
| `is_cancelled`             | `None`                         | `bool`          | Returns `True` if the order state is cancelled.                                                                         |
| `from_json`                | data: `Dict[str, Any]`         | `InFlightOrder` | Converts the order data from a JSON object to an `InFlightOrder` object.                                                |
| `update_with_trade_update` | trade_update: `Dict[str, Any]` | `bool`          | Updates the in flight order with trade update from the REST or WebSocket API. Returns `True` if the order gets updated. |

### Exchange Class

The `Exchange` class is the middle-man between the strategies and the exchange API servers. It provides the necessary order book and user data to the strategies and communicates the order proposals to the exchanges.

The functions of the `Exchange` class can be catergorized into:

[**(1) Placing Orders**](#1-placing-orders)<br/>
[**(2) Cancelling Orders**](#2-cancelling-orders)<br/>
[**(3) Tracking Orders & Balances**](#3-tracking-orders--balances)<br/>
[**(4) Managing Trading Rules**](#4-managing-trading-rules)<br/>
[**(5) Additional Functions**](#5-additional-functions)<br/>
[**(6) Class Properties**](#6-class-properties)

Although this might seem pretty straightforward, it does require a certain level of understanding and knowing the expected side-effect(s) of certain functions.

The **_Exchange Class Diagram_**, given below, details the critical variables and functions in the `Exchange` class.

![ExchangeUMLDiagram](/assets/img/exchange-class.svg)

!!! note
    The 6 categories of functions broadly covers the necessary functions that need to be implemented in the `Exchange` class, so feel free to include other utility functions as needed.

### (1) Placing Orders

The `Exchange` class places orders by either calling the [`buy()`](#buy) or [`sell()`](#sell) method.
Both these methods first generate a client order ID for the order, which will be used locally by Hummingbot to track the orders before calling the [`_create_order()`](#async-_create_order) method.

#### `buy()`

The function that takes the strategy inputs generates a client order ID(used by Hummingbot for local order tracking) and places a **buy** order by calling the [`_create_order()`](#async-_create_order) function.

**Input Parameter(s):**

| Parameter(s)   | Type        | Description                                                                               |
| -------------- | ----------- | ----------------------------------------------------------------------------------------- |
| `trading_pair` | `str`       | Name of the trading pair symbol(in Hummingbot's format i.e. `BASE-QUOTE`)                 |
| `price`        | `Decimal`   | Price in which the order will be placed in `Decimal`                                      |
| `amount`       | `Decimal`   | Amount in which the order will be placed in `Decimal`                                     |
| `order_type`   | `OrderType` | Specifies the order type of the order(i.e. `OrderType.LIMIT` and `OrderType.LIMIT_MAKER`) |

**Expected Output(s):** order_id: `str`

| Output(s)  | Type  | Description     |
| ---------- | ----- | --------------- |
| `order_id` | `str` | Client Order ID |

#### `sell()`

The function that takes the strategy inputs generates a client order ID(used by Hummingbot for local order tracking) and places a **sell** order by calling the [`_create_order()`](#async-_create_order) function.

**Input Parameter(s):**

| Parameter(s)   | Type        | Description                                                                               |
| -------------- | ----------- | ----------------------------------------------------------------------------------------- |
| `trading_pair` | `str`       | Name of the trading pair symbol(in Hummingbot's format i.e. `BASE-QUOTE`)                 |
| `price`        | `Decimal`   | Price in which the order will be placed in `Decimal`                                      |
| `amount`       | `Decimal`   | Amount in which the order will be placed in `Decimal`                                     |
| `order_type`   | `OrderType` | Specifies the order type of the order(i.e. `OrderType.LIMIT` and `OrderType.LIMIT_MAKER`) |

**Expected Output(s):**

| Output(s)  | Type  | Description     |
| ---------- | ----- | --------------- |
| `order_id` | `str` | Client Order ID |

<!-- 
<details>
  <summary><p style="display:inline"><strong>Input Parameter(s):</strong></p></summary>


| Parameter(s)   | Type        | Description                                                                               |
| -------------- | ----------- | ----------------------------------------------------------------------------------------- |
| `trading_pair` | `str`       | Name of the trading pair symbol(in Hummingbot's format i.e. `BASE-QUOTE`)                 |
| `price`        | `Decimal`   | Price in which the order will be placed in `Decimal`                                      |
| `amount`       | `Decimal`   | Amount in which the order will be placed in `Decimal`                                     |
| `order_type`   | `OrderType` | Specifies the order type of the order(i.e. `OrderType.LIMIT` and `OrderType.LIMIT_MAKER`) |

</details>


<details>
  <summary><p style="display:inline"><strong>Expected Output(s):</strong></p></summary> 

</details>
-->


#### **_async_** `_create_order()`

This function is responsible for executing the API request to place the order on the exchange. It does the following:

- Verifies that the order satisfies exchange trading rules.
- Quantize the order amount to ensure that the precision is as required by the exchange.
- Create a `params` dictionary with the necessary parameters for the desired order.
- Pass the `params` to an `Auth` object to generate the request signature.
- Begin tracking the order by calling [`start_tracking_order(...)`](#start_tracking_order).
- Places the order by calling the [`_api_request()`](#async-_api_request) method with the relevant order parameters.
- Upon successfully placing the order, the tracked order will be updated with the resulting **_exchange order ID_** from the API Response.

!!! note
    The tracked order is an `InFlightOrder` that is within a dictionary variable(`_in_flight_orders`) in the `Exchange` class. `InFlightOrder` are Hummingbot's internal records of orders it has placed that remain open in the exchange. When such orders are either filled or canceled, they are removed from the dictionary by calling [stop_tracking_order()](#stop_tracking_order) method, and the relevant event completion flag is passed to the strategy module.

**Input Parameter(s):**

| Parameter(s)   | Type                                                                                                       | Description                                                                               |
| -------------- | ---------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `order_id`     | `str`                                                                                                      | ID used to track an order in Hummingbot.                                                  |
| `trading_pair` | `str`                                                                                                      | Name of the trading pair symbol(in Hummingbot's format i.e. `BASE-QUOTE`)                 |
| `price`        | `Decimal`                                                                                                  | Price in which the order will be placed in `Decimal`                                      |
| `amount`       | `Decimal`                                                                                                  | Amount in which the order will be placed in `Decimal`                                     |
| `order_type`   | [`OrderType`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py#L61-L69) | Specifies the order type of the order(i.e. `OrderType.LIMIT` and `OrderType.LIMIT_MAKER`) |
| `trade_type`   | [`TradeType`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py#L61-L69) | Specifies the trade type of the order(i.e. `TradeType.BUY` and `TradeType.SELL`)          |

**Expected Output(s):**

| Output(s)  | Type  | Description     |
| ---------- | ----- | --------------- |
| `order_id` | `str` | Client Order ID |

### (2) Cancelling Orders

The strategy and the `exit` command cancels orders by calling [`cancel()`](#cancel) or [`cancel_all()`](#async-cancel_all) methods respectively.

#### `cancel()`

The function that takes in the trading pair and client order ID from the strategy as inputs and proceeds to a **cancel** the order by calling the [`_execute_cancel()`](#async-_execute_cancel) function.

**Input Parameter(s):**

| Parameter(s)   | Type  | Description                                                               |
| -------------- | ----- | ------------------------------------------------------------------------- |
| `trading_pair` | `str` | Name of the trading pair symbol(in Hummingbot's format i.e. `BASE-QUOTE`) |
| `order_id`     | `str` | Client Order ID                                                           |

**Expected Output(s):** order_id: `str`

#### **_async_** `cancel_all()`

The function that is primarily triggered by the `ExitCommand` that **cancels all** `InFlightOrder's being tracked by the `Exchange` class. It confirms the successful cancellation of the orders by calling the

Calls the [\_api_request()](#async-_api_request) function with the relevant parameters.

**Input Parameter(s):** `None`

**Expected Output(s):**

| Output(s)             | Type                       | Description                                                                                                                                                    |
| --------------------- | -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cancellation_result` | `List[CancellationResult]` | List of `CancellationResult`. `CancellationResult.success` is assigned `True` if the particular order(identified by Client Order ID) is successfully cancelled |

!!! note
    In some cases, where an exchange does not have a cancel all orders endpoint, the we will have to call `_execute_cancel()` for each in-flight order.

#### **_async_** `_execute_cancel()`

Cancels the specified in-flight order and returns the client order ID.

**Input Parameter(s):**

| Parameter(s)   | Type  | Description                                                               |
| -------------- | ----- | ------------------------------------------------------------------------- |
| `trading_pair` | `str` | Name of the trading pair symbol(in Hummingbot's format i.e. `BASE-QUOTE`) |
| `order_id`     | `str` | Client Order ID                                                           |

**Expected Output(s):**

| Output(s)  | Type  | Description     |
| ---------- | ----- | --------------- |
| `order_id` | `str` | Client Order ID |

### (3) Tracking Orders & Balances

The functions listed in this section details how the connector should process and track orders and balances.

#### `start_tracking_order()`

Starts tracking an order by simply adding it into `_in_flight_orders` dictionary.

**Input Parameter(s):**

| Parameter(s)        | Type                                                                                                       | Description                                                                               |
| ------------------- | ---------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `order_id`          | `str`                                                                                                      | ID used to track an order in Hummingbot.                                                  |
| `exchange_order_id` | `str`                                                                                                      | ID used to uniquely identify the order on the Exchange.                                   |
| `trading_pair`      | `str`                                                                                                      | Name of the trading pair symbol(in Hummingbot's format i.e. `BASE-QUOTE`)                 |
| `price`             | `Decimal`                                                                                                  | Price in which the order will be placed in `Decimal`                                      |
| `amount`            | `Decimal`                                                                                                  | Amount in which the order will be placed in `Decimal`                                     |
| `order_type`        | [`OrderType`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py#L61-L69) | Specifies the order type of the order(i.e. `OrderType.LIMIT` and `OrderType.LIMIT_MAKER`) |
| `trade_type`        | [`TradeType`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py#L61-L69) | Specifies the trade type of the order(i.e. `TradeType.BUY` and `TradeType.SELL`)          |

**Expected Output(s):** `None`

!!! note
    In most cases, the `exchange_order_id` is only provided after the place order APi request is succesfully processed by the exchange. As such, the `exchange_order_id` can be `None` initially. It can be updated later by using the [InFlightOrderBase.update_exchange_order_id()](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/in_flight_order_base.pyx#L77-L79) function.

#### `stop_tracking_order()`

Stops the tracking of order by simply removing it from `_in_flight_orders` dictionary.

**Input Parameter(s):**

| Parameter(s) | Type  | Description                              |
| ------------ | ----- | ---------------------------------------- |
| `order_id`   | `str` | ID used to track an order in Hummingbot. |

**Expected Output(s):** `None`

#### **_async_** `_user_stream_event_listener()`

Wait for new messages from `_user_stream_tracker.user_stream` queue and processes them according to their message channels.
The respective `UserStreamDataSource queues these messages`.

Below are the function(s) called from within `_user_stream_event_listener()` when a message is received.

| Function(s)                                              | Description                           |
| -------------------------------------------------------- | ------------------------------------- |
| [\_process_order_message()](#_process_order_message)     | Process user's order update messages. |
| [\_process_trade_message()](#_process_trade_message)     | Process user's trade messages.        |
| [\_process_balance_message()](#_process_balance_message) | Process user's balance messages.      |

**Input Parameter(s):** `None`

**Expected Output(s):** `None`

#### `_status_polling_loop()`

Periodically update user balances and order status via REST API. This serves as a fallback measure for WebSocket API updates.
Calling of both [\_update_balances()](#_update_balances) and [\_update_order_status()](#_update_order_status) functions is determined by the `_poll_notifier` variable.

`_poll_notifier` is an `asyncio.Event` object that is set in the `tick()` function.
It is set after every `SHORT_POLL_INTERVAL` or `LONG_POLL_INTERVAL` depending on the `last_recv_time` of the `_user_stream_tracker`.

**Input Parameter(s):** `None`

**Expected Output(s):** `None`

#### `_update_balances()`

Calls the REST API to update total and available balances.

**Input Parameter(s):** `None`

**Expected Output(s):** `None`

#### `_update_order_status()`

Calls the REST API to get order/trade updates for each in-flight order.

If needed, it will call either [\_process_order_message()](#_process_order_message) or [\_process_trade_message()](#_process_trade_message) or both.

!!! note
    `_process_trade_message()` must be called before `_process_order_message()` for any in-flight orders. Each partial fill should be accompanied by a call to `_process_trade_message()`. This ensures that Hummingbot captures every trade executed on an order.

**Input Parameter(s):** `None`

**Expected Output(s):** `None`

#### `_process_order_message()`

Updates the in-flight order's order status and triggers the `OrderCancelledEvent` if needed.

**Input Parameter(s):**

| Parameter(s) | Type             | Description                                           |
| ------------ | ---------------- | ----------------------------------------------------- |
| `order_msg`  | `Dict[str, Any]` | The order response from either REST or WebSocket API. |

**Expected Output(s):** `None`

#### `_process_trade_message()`

Updates in-flight order trade information by calling the `NewInFlightOrder.update_with_trade_update()` function and triggers the `OrderFilledEvent` .

It will also trigger either `BuyOrderCompletedEvent` or `SellOrderCompletedEvent` if needed.

**Input Parameter(s):**

| Parameter(s) | Type             | Description                                                   |
| ------------ | ---------------- | ------------------------------------------------------------- |
| `order_msg`  | `Dict[str, Any]` | The trade history response from either REST or WebSocket API. |

**Expected Output(s):** `None`

#### `_process_balance_message()`

Updates the user's available and total asset balance.

**Input Parameter(s):**

| Parameter(s)  | Type             | Description                                                  |
| ------------- | ---------------- | ------------------------------------------------------------ |
| `balance_msg` | `Dict[str, Any]` | The user balance response from either REST or WebSocket API. |

**Expected Output(s):** `None`

### (4) Managing Trading Rules

The `Exchange` is also responsible for managing the trading rules of the trading pairs since the exchange itself enforces rules.

Below are the functions used to ensure that orders being placed meet the requirements and ensure that the trading rules are up to date.:

#### **_async_** `_trading_rules_polling_loop()`

An asynchronous task that periodically updates trading rules.

Calls [`_update_trading_rules()`](#async-_update_trading_rules)

**Input Parameter(s):** `None`

**Expected Output(s):** `None`

#### **_async_** `_update_trading_rules()`

Queries the necessary API endpoint and initialize the `TradingRule` object for each trading pair being traded.

Calls [\_api_request()](#async-_api_request) and subsequently [`_format_trading_rules()`](#_format_trading_rules)

**Input Parameter(s):** `None`

**Expected Output(s):** `None`

#### `_format_trading_rules()`

Converts JSON API response into a dictionary of [`TradingRule`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/trading_rule.pyx).

**Input Parameter(s):**

| Parameter(s)   | Type             | Description                                           |
| -------------- | ---------------- | ----------------------------------------------------- |
| `api_response` | `Dict[str, Any]` | The JSON API response for the exchanges trading rules |

**Expected Output(s):** `None`

!!! note
    The trading rules can generally be found in the API endpoint that lists all supported trading pairs/markets.

#### `get_order_price_quantum()`

Returns a price step, a minimum price increment for a given trading pair.

**Input Parameter(s):**

| Parameter(s)   | Type      | Description                             |
| -------------- | --------- | --------------------------------------- |
| `trading_pair` | `str`     | Trading pair of the order being placed. |
| `price`        | `Decimal` | Price of the order being placed.        |

**Expected Output(s):**

| Output(s)             | Type      | Description                                       |
| --------------------- | --------- | ------------------------------------------------- |
| `min_price_increment` | `Decimal` | Minimum Price increment of specified trading pair |

#### `get_order_size_quantum()`

Returns an order amount step, a minimum amount increment for a given trading pair.

**Input Parameter(s):**

| Parameter(s)   | Type      | Description                             |
| -------------- | --------- | --------------------------------------- |
| `trading_pair` | `str`     | Trading pair of the order being placed. |
| `order_size`   | `Decimal` | Order size of the order being placed.   |

**Expected Output(s):**

| Output(s)       | Type      | Description                                                 |
| --------------- | --------- | ----------------------------------------------------------- |
| `min_increment` | `Decimal` | Minimum base asset size increment of specified trading pair |

### (5) Additional Function(s)

The list below contains the utility functions and descriptions that the `Exchange` class use.

#### **_async_** `_api_request()`

#### `start_network()`

This function is required by the `NetworkIterator` base class and is called automatically.
It starts tracking order books, polling trading rules, updating statuses, and tracking user data.

**Input Parameter(s):** `None`

**Expected Output(s):** `None`

#### `stop_network()`

This function is required by the `NetworkIterator` base class and is called automatically.
It performs the necessary shut down procedure.

**Input Parameter(s):** `None`

**Expected Output(s):** `None`

#### `check_network()`

This function is required by NetworkIterator base class and is called periodically to check the network connection.
Ping the network (or call any lightweight public API).

**Input Parameter(s):** `None`

**Expected Output(s):** `None`

#### `get_order_book()`

They are used by the `OrderBookCommand` to display the order book in the terminal.

**Input Parameter(s):**

| Parameter(s)   | Type  | Description                                                               |
| -------------- | ----- | ------------------------------------------------------------------------- |
| `trading_pair` | `str` | Trading pair used to identify the `OrderBook` from the `OrderBookTracker` |

**Expected Output(s):**

| Output(s)    | Type        | Description                                      |
| ------------ | ----------- | ------------------------------------------------ |
| `order_book` | `OrderBook` | `OrderBook` object of the specified trading pair |

#### `get_open_orders()`

Queries the open order endpoint and parses the response as a `List` of `OpenOrder` objects.

**Input Parameter(s):** `None`

**Expected Output(s):**

| Output(s) | Type              | Description         |
| --------- | ----------------- | ------------------- |
| `orders`  | `List[OpenOrder]` | List of open orders |

#### `restore_tracking_states()`

Restore in-flight orders from saved tracking states; this is such that the connector can pick up on where it left off should it crash unexpectedly.

The saved tracking states are stored locally as a `sqlite` file in the `/data` folder.

**Input Parameter(s):**

| Parameter(s)   | Type             | Description                                                                  |
| -------------- | ---------------- | ---------------------------------------------------------------------------- |
| `saved_states` | `Dict[str, any]` | JSON value of all the saved order states from the locally saved sqlite file. |

**Expected Output(s):** `None`

#### `supported_order_types()`

Returns list of OrderType supported by this connector.

**Input Parameter(s):** `None`

**Expected Output(s):**

| Output(s) | Type              | Description                                                                                           |
| --------- | ----------------- | ----------------------------------------------------------------------------------------------------- |
| `types`   | `List[OrderType]` | List of `OrderType`. Generally connectors would support `OrderType.LIMIT` and `OrderType.LIMIT_MAKER` |

#### **_async_** `_http_client`

Returns the shared `aiohttp.ClientSession` used by the connector. This HTTP client is used for all REST API requests.

**Input Parameter(s):** `None`

**Expected Output(s):**

| Output(s) | Type                    | Description                                                    |
| --------- | ----------------------- | -------------------------------------------------------------- |
| `client`  | `aiohttp.ClientSession` | A HTTP client used to interact with the exchanges API servers. |

#### `get_fee()`

To get trading fee, this function is simplified by using a fee override configuration. Most parameters to this function are ignored except order_type.
Use `OrderType.LIMIT_MAKER` to specify you want a trading fee for the maker order.

**Input Parameter(s):**

| Parameter(s)     | Type                                                                                                       | Description                                                                               |
| ---------------- | ---------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `base_currency`  | `str`                                                                                                      | Base currency of the order.                                                               |
| `quote_currency` | `str`                                                                                                      | Quote currency of the order.                                                              |
| `price`          | `Decimal`                                                                                                  | Price in which the order will be placed in `Decimal`                                      |
| `amount`         | `Decimal`                                                                                                  | Amount in which the order will be placed in `Decimal`                                     |
| `order_type`     | [`OrderType`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py#L61-L69) | Specifies the order type of the order(i.e. `OrderType.LIMIT` and `OrderType.LIMIT_MAKER`) |
| `trade_type`     | [`TradeType`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py#L61-L69) | Specifies the trade type of the order(i.e. `TradeType.BUY` and `TradeType.SELL`)          |

**Expected Output(s):**

| Output(s) | Type                                                                                                        | Description                       |
| --------- | ----------------------------------------------------------------------------------------------------------- | --------------------------------- |
| `fee`     | [`TradeFee`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py#L257-L287) | Estimated trade fee of the order. |

### (6) Class Properties

Below are the property functions of the `Exchange` class.

| Property Function(s) | Output                     | Description                                                                                                                       |
| -------------------- | -------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `name`               | `str`                      | Name of the exchange. Used to identify the exchange across Hummingbot.                                                            |
| `order_books`        | `Dict[str, OrderBook]`     | Dictionary of the `OrderBook` of each active trading pair on the bot. Utilizes the `order_books` property from `OrderBookTracker` |
| `trading_rules`      | `Dict[str, TradingRule]`   | Returns the `_trading_rule` class variable; a dictionary of the `TradingRule` of each active trading pair on the bot.             |
| `in_flight_orders`   | `Dict[str, InFlightOrder]` | Dictionary of the all `InFlightOrder` by its client order ID.                                                                     |
| `status_dict`        | `Dict[str, bool]`          | A dictionary of statuses of various connector's components. Used by the `ready()` property function.                              |
| `ready`              | `bool`                     | True when all statuses pass, this might take 5-10 seconds for all the connector's components and services to be ready.            |
| `limit_orders`       | `List[LimitOrder]`         | Returns a list of `InFlightOrder`.                                                                                                |
| `tracking_states`    | `Dict[str, Any]`           | All `InFlightOrder` in JSON format. Used to save in sqlite db.                                                                    |

## Debugging & Testing

As part of the QA process, for each task (Task 1 through 3), you are **required** to include the unit test cases for the code review process to begin. Refer to [Option 1: Unit Test Cases](/developer/debug&test/#option-1-unit-test-cases) to build your unit tests.
