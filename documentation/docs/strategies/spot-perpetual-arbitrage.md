# Spot Perpetual Arbitrage

!!! warning
    This experimental strategy has undergone code review, internal testing and was shipped during one of our most recent releases. As part of User Acceptance Testing, we encourage users to report any issues and/or provide feedback with this strategy in our [Discord server](https://discord.com/invite/2MN3UWg) or [submit a bug report](https://github.com/CoinAlpha/hummingbot/issues/new?assignees=&labels=bug&template=bug_report.md&title=)

## How it works

This strategy looks at the price on the spot connector and the price on the derivative connector. Then it calculates the spread between the two connectors. The key features for this strategy are `min_divergence` and `min_convergence`.
When the spread between spot and derivative markets reaches a value above `min_divergence`, the first part of the operation will be executed, creating a buy/sell order on the spot connector, while opening an opposing long/short position on the derivative connector.
With the position open, the bot will scan the prices on both connectors, and once the price spread between them reaches a value below `min_convergence`, the bot will close both positions.

## Prerequisites

- You will need some quote assets for orders to be opened

- Some xDai for gas when using Perpetual Finance connector. See this [link](https://bridge.xdaichain.com/) for more info.

- [Hummingbot Gateway](/gateway/installation/) if using Perpetual Finance connector

## Basic parameters

The following walks through all the steps when running the `create` command.

### `spot_connector`

Enter an exchange you would like to trade on.

** Prompt: **

```json
Enter a spot connector (Exchange/AMM)
>>> binance
```

### `spot_market`

Enter the token trading pair for the spot exchange.

** Prompt: **

```json
Enter the token trading pair you would like  to trade on binance (e.g ETH-USDT)
>>> ETH-USDT
```

### `derivative_connector`

Enter the derivative exchange you would like to trade on.

** Prompt: **

```json
Enter a derivative name (Exchange/AMM)
>>> binance_perpetuals
```

### `derivative_market`

Enter the token trading pair for the derivative exchange.

** Prompt: **

```json
Enter the token trading pair you would like  to trade on binance_futures (e.g ETH-USDC)
>>> ETH-USDC
```

### `order_amount`

The order amount for both the orders. Ensure you have enough balance on quote tokens to place orders.

** Prompt: **

```json
What is the amount of ETH per order?
>>>
```

### `derivative_leverage`

Enter the leverage you would like to use.

** Prompt: **

```json
How much leverage would you like to use on the derivative exchange? (Enter 1 to indicate 1x)
>>> 1
```

### `min_divergence`

The spread required for the first part of the arbitrage to be executed.

** Prompt: **

```json
What is the minimum spread between the spot and derivative market price before starting an arbitrage? (Enter 1 to indicate 1%)
>>> 1
```

### `min_convergence`

The spread required for the second part of the arbitrage to be executed.

** Prompt: **

```json
What is the minimum spread between the spot and derivative market price before closing an existing arbitrage? (Enter 1 to indicate 1%)
>>> 0.01
```

### `maximum_funding_rate`

If set to True, the strategy will not execute second arbitrage during the funding period until funding payment is received. If set to False, second arbitrage will be executed depending of the funding payment time.

** Prompt: **

```json
Would you like to take advantage of the funding rate on the derivative exchange, even if min convergence is reached during funding time? (True/False)
>>> False
```

### `spot_market_slippage_buffer`

Percent buffer added to the spot exchange price to account for price movement before trade execution.

** Prompt: **

```json
How much buffer do you want to add to the price to account for slippage for orders on the spot market (Enter 1 for 1%)?
>>> 0.05
```

### `derivative_market_slippage_buffer`

Percent buffer added to the derivative exchange price to account for price movement before trade execution.

** Prompt: **

```json
How much buffer do you want to add to the price to account for slippage for orders on the derivative market (Enter 1 for 1%)?
>>> 0.05
```
