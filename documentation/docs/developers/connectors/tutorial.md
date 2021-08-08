# Tutorial - How to Build a Connector

!!! note "Important changes by release"
    This [page](https://www.notion.so/hummingbot/a26c8bcf30284535b0e5689d45a4fe88?v=869e73f78f0b426288476a2abda20f2c) lists all relevant updates to Hummingbot codebase aimed to help connector developers in making the requisite changes to their connectors.

Each exchange connector is comprised of the following key functions:

| Functions                         | Description                                                                 |
| --------------------------------- | --------------------------------------------------------------------------- |
| **(1) Placing/Cancelling Orders** | Sending buy/sell/cancel instructions to the exchange.                       |
| **(2) Order book tracking**       | Tracking exchange's real-time order book data.                              |
| **(3) Parsing order book data**   | Formatting raw order book data into the standard format used by Hummingbot. |
| **(4) Active order tracking**     | Tracking orders placed by the bot on the exchange.                          |
| **(5) User stream tracker**       | Tracking user data specific to the current user of the bot.                 |

## Getting Started

This guide will help you learn about the basic structure of a connector in Hummingbot. Included in this guide is the scope of creating/modifying the necessary components to implement an exchange connector.

By the end of this guide, you should:

- Have a general understanding of the base classes that serve as building blocks of a connector
- Be able to integrate new connectors from scratch

Implementing a new connector can generally be split into 3 major tasks:

- **Task 1:** [OrderBookDataSource & OrderBookTracker](task1)
- **Task 2:** [UserStreamDataSource, UserStreamTracker & Auth](task2)
- **Task 3:** [Exchange Connector](task3)

## Tasks and UML Diagram

The following diagram displays the tasks and their relevant classes as a checklist to get started.

![connector tutorial UML](/assets/img/connector-tutorial-uml.svg)

## Order Lifecycle and Market Events

Exchange connectors track status updates of all orders created in Hummingbot and emit events on status updates of its orders for the strategy modules.
Be careful when implementing a new exchange connector to ensure all the status updates and emitted events adhere to the semantics defined by Hummingbot.

### Order Tracking

Order tracking starts when `_create_order()` is called. It is called from within the `buy()` and `sell()` functions.
An exchange connector should keep tracking the order's status and emit events for any change of states until the order is completed, cancelled, expired, or failed.

!!! note
    This is done by calling `start_tracking_order()` method in the #Exchange# class. `start_tracking_order()` should be called before the API request for placing the order is executed.

### Order Lifecycle Flowchart

![Figure 1: Order lifecycle flowchart](/assets/img/connector-order-lifecycle.svg)

### Creating an Order

An order is created by invoking `buy()` or `sell()` in an exchange connector - usually by a strategy module.
`buy()` and `sell()` would return immediately with a client-side order ID that Hummingbot uses to track the order's status.
They would schedule the order to be submitted to the exchange as soon as possible but would not wait for the reply from the exchange before returning.

### Submitting an Order

In most of our built-in exchange connectors, order submission occurs in the `_create_order()` function - although it may be different for some decentralized exchange connectors.

The `_create_order()` method is responsible for performing the necessary trading rule checks before submitting the order via the REST API.
Upon receiving a successful response, a `BuyOrderCreatedEvent` or `SellOrderCreatedEvent` would be emitted. Otherwise, a `MarketOrderFailureEvent` would be emitted. Note that despite the naming, `MarketOrderFailureEvent` is emitted even for limit orders.

### Order Being Filled

Other market participants could fill an order over time once it's live on an exchange.
Depending on the order types, i.e. limit or market, the order could be filled either immediately or after another market participant fulfils it.

For every order fill on our orders, whether partially or entirely, the exchange connector must emit an `OrderFilledEvent`, to notify the strategy modules about the order's progress.

### Order Completion

Once an order has been completely filled, the exchange connector must emit a `BuyOrderCompletedEvent` or `SellOrderCompletedEvent`.
The exchange connector would stop tracking the order afterward.

`BuyOrderCompletedEvent` or `SellOrderCompletedEvent` should always come **after** an `OrderFilledEvent` has been emitted.

### Order Cancellation or Expiry

If an order is canceled or expired before it has been completely filled, an `OrderCancelledEvent` or an `OrderExpiredEvent` should be emitted.

For centralized exchanges, order tracking should end after emitting an `OrderCancelledEvent` or `OrderExpiredEvent`.
On decentralized exchanges - since it's possible for orders to be filled after cancellation or even expiry, due to block delays - the exchange connector may keep tracking the order for a certain amount of time afterwards.

### Order Failure

If a failed order has been rejected for any reason other than cancellation or expiry, `MarketOrderFailureEvent` must be emitted.

## InFlightOrder Helper

Hummingbot comes with a built-in helper class for exchange connectors to track their order status, the `InFlightOrderBase` class.

![Figure 2: InFlightOrderBase class](/assets/img/connector-in-flight-uml.svg)

While developers are free to extend or modify from `InFlightOrderBase` to suit their logic. There are a few conventions within Hummingbot's built-in exchange connectors for extending `InFlightOrderBase`,
and it is recommended that new exchange connectors should stick with the same conventions.

Below are some of the functions that are required to be implemented in the new exchange connector.

- `is_done: bool`

  This property indicates whether the order is done or not, whether it has been filled or failed, canceled or expired.

- `is_cancelled: bool`

  This property indicates whether the order has been canceled or not.

- `is_failure: bool`

  This property indicates whether the order has been terminated before completion or not. This includes all cases like order cancellation, expiry, or rejection.

- `base_asset: str`

  The base asset symbol.

- `quote_asset: str`

  The quote asset symbol.

- `update_exchange_order_id(str): void`

  This is called when the market connector has successfully submitted the order to the exchange and has got back an exchange-native order ID. This notifies any coroutines waiting on the `get_exchange_order_id()` function (detailed below\).

- `async get_exchange_order_id(): str`

  Returns the exchange-native order ID for the order if the order has been submitted and the exchange-native order ID is known.
  Otherwise, it would wait until `update_exchange_order_id(str)` is called by the market connector.

- `to_limit_order(): LimitOrder`

  Converts the in-flight order data structure to a `LimitOrder` data object. This should only be used on limit orders.

- `to_json(): Dict[str, any]`

  Convert the in-flight order data structure to a dictionary that can be serialized into JSON format.

- `from_json(): Dict[str, Any]`

  Convert a dictionary object containing the relevant order details into an `InFlightOrder` data structure.
