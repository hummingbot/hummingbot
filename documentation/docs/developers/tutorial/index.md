# Developer Tutorial

## Introduction
This tutorial is intended to get you familiarized with basic structure of a strategy for Hummingbot. It will guide you through the scope of creating a simple strategy that only fetches market status to building a more complex strategy that can perform trade.

By the end of this tutorial, you should: 

* Have a general understanding of the base classes that serve as building blocks of the strategies
* Have a working strategy 
* Be able to build new custom strategies from scratch

## What is a strategy?

An algorithmic trading strategy, or "bot", is an automated process that creates/cancels orders, executes trades, and manages positions on crypto exchanges. Like a computer program, a strategy enables traders to respond automatically and continually to market conditions.

We will start by building simple strategies that build upon one another. This should expose you to different parts of the Hummingbot codebase, help you understand some core classes that are frequently referred to when building strategies, and provide a starting point for developing custom strategies. 

## Strategy folder

Each strategy is contained in its own folder, with the strategy name as the folder name:

* **\_\_init__.py**  
This file allows one to expose certain variables to all modules inside the package by placing the strategy object under `__all__`  field.
* **{strategy name}.pxd**  
This file contains type declaration about some variables that are specified in the `{strategy name}.pyx` file.
* **{strategy name}.pyx**  
This file contains a bulk of functions that define the behavior of strategy. The `__init__` function defines the variables that were declared in the `{strategy name}.pxd` file and initializes fields inherited from `StrategyBase` class. All other functions can be customized depending on the behavior that the developer wants to create. A function that is especially important is `format_status()` because this function chooses which data to render when `status` is called on the client.
* **{strategy name}_config_map.py**  
This file handles prompting user for config values when the strategy is called. Each key value of the `config_map` has a `ConfigVar` assigned where developer can specify the prompt and assign validators to check for accepted values.
* **start.py**  
The `start()` function is what gets called when user calls the strategy on client side. This function should handle initialization of configs by calling `config_map`, set market names and wallets, and eventually execute the strategy.

## StrategyBase class
All strategies extend `StrategyBase` class. This class allows extraction of logic that would be repetitively written in all strategies otherwise. 

* **Event listeners** : The client’s prompt eventually leads to changes on server with the help of event listeners. Depending on action taken by the client, corresponding event listeners are called to execute the appropriate job.
* **Data frames** : The base class handles creation of data frames for market status, `market_status_data_frame()`, and wallet balance, `wallet_balance_data_frame()`, so it is easy for developers to create and access about particular markets.

The base class also contains methods that are meant to be freshly implemented when new strategies are created.

* `logger()` : set up logger for strategy session
* `format_status()` : define format of status that will be rendered on Hummingbot client

To assist in the development of custom strategies, there are many overridable functions that respond to various events detected by EventListeners. 

* `c_did_create_buy_order()`: called in response to an `order_created_event`
* `c_did_create_sell_order()`: called in response to an `order_created_event`
* `c_did_fail_order()`: called in response to an `order_filled_event`
* `c_did_create_sell_order()`: called in response to an `order_failed_event`
* `c_did_cancel_order()`: called in response to a `cancelled_event`
* `c_did_expire_order()`: called in response to an `expired_event`
* `c_did_complete_buy_order()`: called in response to an `order_completed_event`
* `c_did_complete_sell_order()`: called in response to an `order_completed_event`
* `c_did_fail_order_tracker()`: called in response to an `order_failed_event`
* `c_did_cancel_order_tracker()`: called in response to an `order_cancelled_event`
* `c_did_expire_order_tracker()`: called in response to an `order_expired_event`
* `c_did_complete_buy_order_tracker()`: called in response to an `order_completed_event`
* `c_did_complete_sell_order_tracker()`: called in response to an `order_completed_event`

## Market class

The `market_base` class contains overridable functions that can help get basic information about an exchange that a strategy is operating on, which can include the balance, prices, and order books for any particular asset traded on the exchange. 

* `c_buy()`: called when the user wants to place a buy order
* `c_sell()`: called when the user wants to place a sell order
* `c_cancel()`: called when the user wants to place an order cancellation
* `c_get_balance()`: called to get the user’s balance of assets
* `c_get_available_balance()`: called to get the user’s available balance of assets
* `c_withdraw()`: called when the user wants to withdraw assets
* `c_get_order_book()`: called to get the order book for any particular asset
* `c_get_price()`: called to get the price for any particular asset
* `c_get_order_price_quantum()`: called to get the quantum price of an order
* `c_get_order_size_quantum()`: called to get the quantum size of an order
* `c_quantize_order_price()`: called to quantize the price of an order
* `c_quantize_order_amount()`: called to quantize the amount of an order
* `c_get_fee()`: called to get the fee for exchange use

Additionally, this strategy leverages the `Market` class’s `EventReporter` listener object, in order to check if buy/sell orders have been filled or completed, the user has enough balance to place certain orders, and if there are any order cancellations. The `EventLogger` object is also used to log the specific events when they occur. 

## Configuration

### Important commands
Important commands on Hummingbot client:

* `status` : Renders information about the current strategy and markets. The information that you want displayed can be customized with `format_status()` function in `{strategy name}.pyx`
* `config` : Prompts users asking for details about strategy set up (e.g. token, market name, etc). Prompts can be modified in `{strategy name}_config_map.py`

### Exposing new strategy to Hummingbot client
Make strategy name known to the client by adding name to [hummingbot/client/settings.py](https://github.com/CoinAlpha/hummingbot/blob/development/hummingbot/client/settings.py) under `STRATEGIES` variable. There should also be a template file that contains config variables and its documentation in the [hummingbot/templates](https://github.com/CoinAlpha/hummingbot/tree/development/hummingbot/templates) directory. The naming convention for this yml file is `conf_{strategy name}_TEMPLATE`. 

### Setting question prompts for strategy parameters
Strategy parameters can be set in the `config_map` file. Each parameter (represented as dictionary key) is mapped to a `ConfigVar` type where developer can specify the name of the parameter, prompts that will be provided to the user, and validator that will check the values entered. 

<!-- ## 2. Get Order Book Strategy
We will extend on what we built on step 1 and add a feature that will load the order book for a market. This part will help developers understand how to read data from different data frames.

#### Order book data
This strategy extends the Hello World Strategy by loading an order book in a given market. When the command `status` is executed, the strategy fetches and enumerates the order book data (maker orders) by retrieving the `active_orders` data frame for the market that the strategy is operating on. If there are no active orders, " No active maker orders." is printed. 
-->

