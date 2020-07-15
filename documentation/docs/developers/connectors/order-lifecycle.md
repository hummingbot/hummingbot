# Order Lifecycle and Market Events

## Introduction

Exchange connectors track status updates of all orders created in Hummingbot, and emit events on status updates of its orders for strategy objects. When implementing a new exchange connector, care must be taken to ensure all the status updates and emitted events adhere to the same semantics as other market connectors.

## Order Tracking

Order tracking starts when `c_buy()` or `c_sell()` is called. It happens for both market order and limit orders. A market connector should keep tracking the status of the order and emit events for any change of states, until the order is completed, cancelled, expired or failed.

### Order Lifecycle Flowchart

![Figure 1: Order lifecycle flowchart](/assets/img/connector-order-lifecycle.svg)

### Creating an Order

An order is created by invoking `c_buy()` or `c_sell()` in a market connector - usually from a strategy object. `c_buy()` and `c_sell()` would return immediately with a client-side order ID that Hummingbot uses to track the order's status. They would schedule the order to be submitted to the exchange as soon as possible, but would not wait for the reply from the exchange before returning.

### Submitting an Order

In most of our built-in market connectors, order submission happens in the functions `execute_buy()` and `execute_sell()` - although it may be different for some decentralized exchange connectors.

`execute_buy()` and `execute_sell()` are different from `c_buy()` and `c_sell()` because they are asynchronous functions - they can make network calls without blocking other code in Hummingbot.

If `execute_buy()` or `execute_sell()` successfully submits an order to the exchange, and gets back a successful reply - then a `BuyOrderCreatedEvent` or `SellOrderCreatedEvent` would be emitted. If the order submission fails, then a `MarketOrderFailureEvent` would be emitted. Note that despite the naming, `MarketOrderFailureEvent` is emitted even for limit orders.

### Order Being Filled

An order would be filled by other market participants over time, once it's live on an exchange. If the order is a limit order, then usually it has to wait for market orders from other market participants to hit it. If the order is a market order, then usually it is filled as soon as possible by getting matched to limit orders on the exchange.

For every order fill related to orders it made before, a market connector must emit a `OrderFilledEvent`, to notify strategy objects about the progress of the order.

### Order Completion

Once an order has been completely filled, the market connector would emit a `BuyOrderCompleted` or `SellOrderCompleted` event. The market connector would stop tracking the order afterwards.

`BuyOrderCompleted` or `SellOrderCompleted` events should always come after the `OrderFilledEvent` that finished filling the order.d

### Order Cancellation or Expiry

If an order is cancelled, or expired before it has been completely filled - then an `OrderCancelledEvent` or an `OrderExpiredEvent` would be emitted.

For centralized exchanges, order tracking should end after emitting an `OrderCancelledEvent` or `OrderExpiredEvent`. On decentralized exchanges - since it's possible for orders to be filled after cancellation or even expiry, due to block delays - the market connector may keep tracking the order for a certain amount of time afterwards.

### Order Failure

On some exchanges, it is possible for an order to fail or rejected without having completed, having been cancelled or expired. For example, on decentralized exchanges, an live order could be rejected by the exchange after initial submission if there is not enough balance on the wallet to fill the order. If an order has failed or has been rejected for any reason other than cancellation or expiry, then a `MarketOrderFailureEvent` would be emitted.


## In Flight Order Helper

Hummingbot comes with a built-in helper class for market connectors to track their order states, the `InFlightOrderBase` class.

![Figure 2: InFlightOrderBase class](/assets/img/connector-in-flight-uml.svg)

While market connector authors are free to extend or modify from `InFlightOrderBase` to suit their own logic. There are a few conventions within Hummingbot's built-in market connectors for extending `InFlightOrderBase`, and it is recommended that new market connectors should stick with the same conventions.

* `is_done: bool`

    This property indicates whether the order is done or not, whether it has been completely filled or failed, cancelled or expired.
  
* `is_cancelled: bool`

    This property indicates whether the order has been cancelled or not.
  
* `is_failure: bool`

    This property indicates whether the order has been terminated before completion or not. This includes all cases like order cancellation, expiry or rejection.
    
* `base_asset: str`

    The base asset symbol.
    
* `quote_asset: str`

    The quote asset symbol.
    
* `update_exchange_order_id(str): void`

    This is called when the market connector has successfully submitted the order to the exchange, and has got back an exchange-native order ID. This notifies any coroutines waiting on the `get_exchange_order_id()` function (detailed below\).
    
* `async get_exchange_order_id(): str`

    This is an asynchronous function and can only be called from `async def` functions in Hummingbot. It returns the exchange-native order ID for the order, if the order has been submitted and the exchange-native order ID is known. Otherwise, it would wait until `update_exchange_order_id(str)` is called by the market connector.
    
* `to_limit_order(): LimitOrder`

    Converts the in-flight order data structure to a `LimitOrder` data object. This should only be used on limit orders.
    
* `to_json(): Dict[str, any]`

    Convert the in-flight order data structure to a dictionary that can be serialized into JSON format.