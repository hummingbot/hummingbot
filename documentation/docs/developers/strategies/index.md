## What is a strategy?

An algorithmic trading strategy, or "bot", is an automated process that creates/cancels orders, executes trades, and manages positions on crypto exchanges. Like a computer program, a strategy enables traders to respond automatically and continually to market conditions.

We will start by building simple strategies that build upon one another. This should expose you to different parts of the Hummingbot codebase, help you understand some core classes that are frequently referred to when building strategies, and provide a starting point for developing custom strategies. 

## Tutorial

The [tutorial](./tutorial) teaches you how to create a Hummingbot strategy that executes a simple limit order.

## Guides

* [Key Concepts](./key-concepts): Basic overview and structure of what goes into a Hummingbot strategy
* [Get Started](https://docs.hummingbot.io/developers/strategies/tutorial/#create-a-strategy): Create a simple strategy that executes a limit order
* [Define Configs](./config): Define configuration parameters
* [Hanging Orders Tracker](./hanging-orders): Learn how to use the hanging order tracker in your strategy

<!-- 
* [Display Status](./status): Customize what is displayed when the user runs the `status` command
* [Access Order Book Data](./order-book): Access real-time order book data from the strategy 
-->
