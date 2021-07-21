---
title: Build Strategy
description: Guide on building a strategy for Hummingbot
---

## Introduction

This tutorial will help you learn the basic structure of a strategy for Hummingbot. It will guide you through the scope of creating a simple strategy that only fetches market status to building a more complex strategy that can perform trades.

By the end of this tutorial, you should:

- Have a general understanding of the base classes that serve as building blocks of the strategies
- Have a working strategy
- Be able to build new custom strategies from scratch

## Hello World Strategy

We will start with a simple strategy that can perform `status` command and displays the user's token balance in a given market. This part should expose you to different parts of the Hummingbot codebase, help you understand some core classes frequently referred to when building strategies, and provide a starting point for developing custom strategies.

#### Directory Breakdown

Take a look at the directory for hello world strategy:

- **\_\_init\_\_.py**  
  This file allows one to expose certain variables to all modules inside the package by placing the strategy object under `__all__` field.
- **{strategy name}.pxd**  
  This file contains a type declaration about some variables that are specified in the `{strategy name}.pyx` file.
- **{strategy name}.pyx**  
  This file contains a bulk of functions that define the behavior of strategy. For example, the `__init__` function defines the variables that were declared in the `{strategy name}.pxd` file and initializes fields inherited from `StrategyBase` class. All other functions can be customized depending on the behavior that the developer wants to create. For example, an essential function is `format_status()` because this function chooses which data to render when `status` is called on the client.
- **{strategy name}\_config_map.py**  
  This file handles prompting the user for config values when the strategy is called. Each key value of the `config_map` has a `ConfigVar` assigned where a developer can specify the prompt and assign validators to check for accepted values.
- **start.py**  
  The `start()` function gets called when the user calls the strategy on the client-side. This function should handle the initialization of configs by calling `config_map`, set market names and wallets, and eventually execute the strategy.

#### Important commands

Important commands on Hummingbot client:

- `status` : Renders information about the current strategy and markets. The information that you want to be displayed can be customized with `format_status()` function in `{strategy name}.pyx`
- `config` : Prompts users asking for details about strategy set up (e.g. token, market name, etc). Prompts can be modified in `{strategy name}_config_map.py`

#### StrategyBase class

All strategies extend the `StrategyBase` class. This class allows extraction of logic that would be repetitively written in all strategies otherwise.

- **Event listeners** : The client's prompt eventually leads to changes on a server with the help of event listeners. Depending on the action taken by the client, corresponding event listeners are called to execute the right job.
- **Data frames** : The base class handles the creation of data frames for market status, `market_status_data_frame()`, and wallet balance, `wallet_balance_data_frame()`, so it is easy for developers to create and access about particular markets.

The base class also contains methods that are meant to be freshly implemented when new strategies are created.

- `logger()` : set up logger for strategy session
- `format_status()` : define format of status that will be rendered on Hummingbot client

To help you develop custom strategies, overridable functions that respond to various events is detected by EventListeners.

- `c_did_create_buy_order()`: called in response to an `order_created_event`
- `c_did_create_sell_order()`: called in response to an `order_created_event`
- `c_did_fail_order()`: called in response to an `order_filled_event`
- `c_did_create_sell_order()`: called in response to an `order_failed_event`
- `c_did_cancel_order()`: called in response to a `cancelled_event`
- `c_did_expire_order()`: called in response to an `expired_event`
- `c_did_complete_buy_order()`: called in response to an `order_completed_event`
- `c_did_complete_sell_order()`: called in response to an `order_completed_event`
- `c_did_fail_order_tracker()`: called in response to an `order_failed_event`
- `c_did_cancel_order_tracker()`: called in response to an `order_cancelled_event`
- `c_did_expire_order_tracker()`: called in response to an `order_expired_event`
- `c_did_complete_buy_order_tracker()`: called in response to an `order_completed_event`
- `c_did_complete_sell_order_tracker()`: called in response to an `order_completed_event`

#### Market class

The `market_base` class contains overridable functions that can help get basic information about an exchange that a strategy is operating on, including the balance, prices, and order books for any particular asset traded on the exchange.

- `c_buy()`: called when the user wants to place a buy order
- `c_sell()`: called when the user wants to place a sell order
- `c_cancel()`: called when the user wants to place an order cancellation
- `c_get_balance()`: called to get the user’s balance of assets
- `c_get_available_balance()`: called to get the user’s available balance of assets
- `c_withdraw()`: called when the user wants to withdraw assets
- `c_get_order_book()`: called to get the order book for any particular asset
- `c_get_price()`: called to get the price for any particular asset
- `c_get_order_price_quantum()`: called to get the quantum price of an order
- `c_get_order_size_quantum()`: called to get the quantum size of an order
- `c_quantize_order_price()`: called to quantize the price of an order
- `c_quantize_order_amount()`: called to quantize the amount of an order
- `c_get_fee()`: called to get the fee for exchange use

Additionally, this strategy leverages the `Market` class's `EventReporter` listener object to check if buy/sell orders have been filled or completed. It also reports if the user has enough balance between placing specific orders and any order cancellations. The `EventLogger` object is used for logging the specific events when they occur.

#### Exposing new strategy to Hummingbot client

Make strategy name known to the client by adding a name to [hummingbot/client/settings.py](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/client/settings.py) under `STRATEGIES` variable. There should also be a template file that contains config variables and its documentation in the [hummingbot/templates](https://github.com/CoinAlpha/hummingbot/tree/development/hummingbot/templates) directory. The naming convention for this yml file is `conf_{strategy name}_TEMPLATE`.

#### Setting question prompts for strategy parameters

Strategy parameters can be set in the `config_map` file. Each parameter (represented as dictionary key) is mapped to a `ConfigVar` type where a developer can specify the parameter's name, prompts that will be provided to the user, and a validator that will check the values entered.

## Get Order Book Strategy

We will extend what we built on step 1 and add a feature that will load the order book for a market. This part will help developers understand how to read data from different data frames.

#### Order book data

This strategy extends the Hello World Strategy by loading an order book in a given market. When the command `status` is executed, the strategy fetches and enumerates the order book data (maker orders) by retrieving the `active_orders` data frame for the market that the strategy is operating on. If there are no active orders, "No active maker orders." is printed.

## Perform Trade Strategy

In the Perform Trade strategy, Hummingbot places a single order that the user specifies. Unlike Simple Trade, orders will not be canceled after a certain amount of time and are only set once at the start of the strategy.

Here's a high-level view of the logic flow inside the built-in perform trade strategy.

![Figure 1: Perform trade strategy flow chart](/img/perform-trade-flowchart.svg)

The flow of the strategy is as follows.

1. Get user input
2. System Checks
3. Place Order

### System Checks & Validation

Before the strategy attempts to perform any trades, it checks the following to ensure it is safe to complete the trade:

1. Are both markets ready and connected?
2. Does the user have enough balance?
   1. Additionally, this check triggers a warning and logs the warning. If the user does not have the requisite balance to perform the trade, the interface will display the warning.
   2. To achieve this check, the Perform Trade strategy gets the user's available balance by using the `c_has_enough_balance()` in [perform_trade.pyx](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/strategy/dev_2_perform_trade/dev_2_perform_trade.pyx).

### Managing Order State

Order state is tracked using the quantity, price, type, id, and other attributes.
The OrderTracker class includes functions monitoring when order tracking begins, noticing and tracking cancels, and tracking ends. When an order is completed, an order id is returned, and the specifics concerning the order can be determined by using the OrderTracker class.

The order state, specifically, whether the order is partially or completely filled is managed by events in the MarketBase class. Specifically, the logic regarding order creation, cancelation, filling, and completion can be found in the following functions in [market_base.pyx](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/market_base.pyx): `buy()`, `sell()`, `cancel()`, `get_order_price_quantum()` (gets the required or allowed order price), and `get_order_size_quantum()` (gets the required or allowed order size).

The order tracking logic can be found in the `c_start_tracking_limit_order()`, `c_stop_tracking_limit_order()`, `c_has_in_flight_cancel()` and `c_check_and_track_cancel()` function inside [order_tracker.pyx](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/order_tracker.pyx).

### Logging

The Perform Trade strategy includes logging operations for info, warnings, and errors. The info logs include information regarding transactions and is logged with severity info. The warning logs include information regarding warnings during a user's session, such as insufficient balance. Finally, the error logs include error information such as the markets being down or unable to connect to the markets and are stored with severity error.

### History

The history command displays fulfilled orders, the balance snapshot, and performance analysis.
Most importantly for this strategy, the completed trades are shown by querying the database to see which transactions have occurred since the start of the session.

The logic for getting the history can be found in the balance_snapshot function, and trades list inside [history_command.py](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/client/command/history_command.py) file.

## Simple trade Strategy

Simple trade strategy expands upon Perform Trade strategy. By the end of this part, you should be able to add:

- time delay between trades
- set a time restriction to cancel order
- implement specific loggings

### Use clock & `c_tick()` to add time restrictions

`c_tick()` : Called everytime a clock 'ticks'

- Check for readiness and connection status of markets with `_all_markets_ready`
- If all markets are ready, call `c_process_market()` on each market.
- Set `_last_timestamp` to current tick's timestamp

NOTE : Can change tick interval by specifying `_tick_size` on the clock. Default = `1.0`

### Add time delay between trades

Ensure that there is a given amount of time in between the trades.

`c_process_market()` : Called on each market from `c_tick()`

- If there is an order to place, check that the current timestamp is greater than the previous Order's timestamp plus delay time (e.g. current timestamp > previous Order's start timestamp + `_time_delay`)
- If current time is valid time to place orders, call `c_place_orders()` to execute the Order

NOTE : Can change delay interval by specifying `_time_delay`. Default = `10.0`

![Figure 1: Processing a new order](/img/Simple_Trade_OrderPlacedRevised.svg)

### Set time to cancel order

Cancel orders once their elapsed times go over a certain amount.

`c_process_market()` : Called on each market from `c_tick()`

- If there are active orders, check if order needs to be canceled (e.g. current_timestamp >= order's start timestamp + `_cancel_order_wait_time`)
- If an order has to be canceled, call `c_cancel_order()` on the corresponding Order

NOTE : Can change cancel interval by specifying `_cancel_order_wait_time`. Default = `60.0`

![Figure 2: Cancelling an order](/img/Simple_Trade_OrderCancelledRevised.svg)

### Logging

When a specific event about the order is triggered, the event handler calls these logging methods to provide helpful information to the users.

- `c_did_fill_order()` — Called when `OrderFilledListener` sees that an order is filled.
- `c_did_complete_buy_order()` — Called when `BuyOrderCompletedListener` sees that a buy order is completed.
- `c_did_complete_sell_order()` — Called when `SellOrderCompletedListener` sees that a sell order is completed.

These functions check to see if the order of interest is market or limit order and outputs appropriate text for each type.

Similar mechanisms can be implemented for the following existing event listeners:

- `OrderFailedListener`
- `OrderCancelledListener`
- `OrderExpiredListener`
- `BuyOrderCreatedListener`
- `SellOrderCreatedListener`
