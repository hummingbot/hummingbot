# Liquidity Mining Strategy

**Updated as of v0.37**

!!! warning
    This experimental strategy has undergone code review, internal testing and was shipped during one of our most recent releases. As part of User Acceptance Testing, we encourage user to report any issues and/or provide feedback with this strategy in our [Discord server](https://discord.com/invite/2MN3UWg) or [submit a bug report](https://github.com/CoinAlpha/hummingbot/issues/new?assignees=&labels=bug&template=bug_report.md&title=)

## How it works

The liquidity mining strategy allows users to market make across multiple markets on an exchange on a single Hummingbot instance. This is achieved by enabling users to configure the markets they would like to participate in and other market-making configurations. Volatility-Spread adjustments are another key feature of this strategy, where the spreads are dynamically adjusted based on the volatility of the markets.

This strategy has parameters like [`volatility_interval`](/strategies/liquidity-mining/#volatility_interval) and [`avg_volatility_period`](/strategies/liquidity-mining/#avg_volatility_period) that automatically adjust the spreads based on a market’s volatility based on the historical mid-price.

Market volatility is calculated using ATR (Average True Range) of historical mid-price. The true range is a difference between the maximum and minimum mid-price value of the period expressed in percentage value.

How to calculate Average True Range of historical mid-price.

![](/assets/img/Average-true-range.png)

The volatility is translated to spread by multiplying it to `volatility_to_spread_multiplier`.

![](/assets/img/adjusted-spread.png)

## Prerequisites

Inventory

You will need to hold a sufficient inventory of quote and base currencies to place orders of the exchange's minimum order size.

Minimum order size

When placing orders, if the order's size determined by the order price and quantity is below the exchange's minimum order size, orders will not be created.

## Basic parameters

The following walks through all the steps when running the `create` command.

### `exchange`

The exchange where the bot will create and place orders.

** Prompt: **

```json
Enter the spot connector to use for liquidity mining?
>>> binance
```

### `markets`

Token trading pair symbols you would like to trade on the exchange.

** Prompt: **

```json
Enter a list of markets (comma separated, e.g. LTC-USDT,ETH-USDT)
>>> ETH-USDT
```

!!! note
    If participating in multiple markets, this strategy only supports trading pairs that share the same base or quote asset.

### `token`

Choose between the base and quote asset wherein you want to provide liquidity. After running the `start` command, the user's balance of `token` is split between all eligible liquidity mining markets on the selected exchange.

** Prompt: **

```json
What asset (base or quote) do you want to use to provide liquidity?
>>> ETH
```

### `order_amount`

The order amount for the limit bid and ask orders. Ensure you have enough balance on base and quote tokens to place the bid and ask orders.

** Prompt: **

```json
What is the size of each order (in ETH amount)?
>>> 0.008
```

### `spread`

The strategy will place the order on a certain % away from the current mid-price. Spreads are automatically adjusted based on the [`volatility_interval`](https://docs.hummingbot.io/strategies/liquidity-mining/#volatility_interval).

** Prompt: **

```json
How far away from the mid-price do you want to place bid and ask orders? (Enter 1 to indicate 1%)
>>> 1
```

### `target_base_pct`

It sets a target of base asset balance in relation to a total asset allocation value (in percentage value). It works the same as the pure market making strategy's [`inventory_skew`](/strategies/inventory-skew/) feature in order to achieve this target. This parameter can be disabled by entering `config inventory_skew_enabled` then set it to `No`.

** Prompt: **

```json
For each pair, what is your target base asset percentage? (Enter 20 to indicate 20%)
>>> 20
```

## Advanced parameters

These are additional parameters that you can reconfigure and use to customize the behavior of your strategy further. To change its settings, run the command `config` followed by the parameter name, e.g. `config volatility_interval`.

See [this page](https://docs.hummingbot.io/operation/config-files/#gatsby-focus-wrapper) for more information how to use `config` command.

### `order_refresh_time`

Value in seconds of the orders’ duration before canceling and creating new sets of orders depending on the current mid-price and spreads at the interval. The default value for the parameter is 10s.

** Prompt: **

```json
How often do you want to cancel and replace bids and asks (in seconds)?
>>> 10
```

### `order_refresh_tolerance_pct`

Determines the tolerance threshold in the percentage of the order price before replacing the orders. This is to prevent replacing the orders too often. The parameter has a default value of 0.2%.

** Prompt: **

```json
Enter the percent change in price needed to refresh orders at each cycle (Enter 1 to indicate 1%)
>>> 0.2
```

### `inventory_skew_enabled`

Allows you to enable and disable the `target_base_pct`. By default, this parameter is set to true.

** Prompt: **

```json
Would you like to enable inventory skew? (Yes/No)
>>> Yes
```

### `inventory_range_multiplier`

This parameter expands the range of tolerable inventory levels on your target base percent as a multiple of your total order size. Larger values expand this range. The predefined value is 1.

** Prompt: **

```json
What is your tolerable range of inventory around the target, expressed in multiples of your total order size?
>>> 1
```

### `volatility_interval`

The interval, in seconds, in which to pick historical data from mid-price to calculate market volatility. The predefined value is 300s.

** Prompt: **

```json
What is an interval, in second, in which to pick historical mid price data from to calculate market volatility?
>>> 300
```

### `avg_volatility_period`

The number of intervals based on `volatility_interval` to calculate the average market volatility. The predefined value is 10.

** Prompt: **

```json
How many interval does it take to calculate average market volatility? 
>>> 10
```

### `volatility_to_spread_multiplier`

This expands the average spread depending on the value set. The predefined value is 1.

** Prompt: **

```json
Enter a multiplier used to convert average volatility to spread (enter 1 for 1 to 1 conversion)
>>> 1
```

### `max_spread`

Sets the maximum spread for your orders. Spreads will not go higher than the value you set for this configuration. By default, this parameter is set to -1.

** Prompt: **

```json
What is the maximum spread? (Enter 1 to indicate 1% or -1 to ignore this setting)
>>> 1
```

### `max_order_age`

Allows you to set a maximum lifespan of your orders (in seconds) at which the orders will certainly get canceled and recreated. Click [here](/strategies/max-order-age/) to learn more about this parameter.

** Prompt: **

```json
What is the maximum life time of your orders (in seconds)?
>>> 3600
```

```json
exchange: binance
markets: ALGO-USDT,AVAX-USDT,FIRO-USDT
token: USDT
order_amount: 15.0
spread: 0.5
target_base_pct: 50%
order_refresh_time: 10
order_refresh_tolerance_pct: 0.2
inventory_range_multiplier: 1.0
volatility_interval: 300
avg_volatility_period: 10
volatility_to_spread_multiplier: 1.0
max_spread: -1.0
max_order_age: 3600.0
```

![](/assets/img/lm.png)

These values will show after running the `status` command. `Budget`, `Markets`, `Miner`, and `Orders`.

!!! note
    `status --live` currently is not compatible with liquidity mining strategy

**Budget**

This table lets you see the markets you are participating in, the balance you currently have, and also the budget allocation for each pair.

**Markets**

This table displays the market, mid-price, best bid, best ask, and volatility. Under the market, it shows the markets chosen to join liquidity mining. The mid-price is the average of the best bid and best ask price in the order book. The best bid and best ask shown above are the best bid and best ask in the order book. The volatility adjustment will apply to your current spread at `order_refresh_time` if the value of the volatility is higher than your current spread.

**Miner**

This shows the markets are chosen, rewards for that certain campaign, rewards per week, current liquidity of that market, yield, and maximum spread for that campaign. This gives you insight on the campaigns you are participating to easily check what are the details for the campaigns.

**Orders**

Other than the markets, this shows the side of the order created, price, current spread, order amount, order size, and the age.

## Sample configurations

Here's an example of how the liquidity mining strategy works.

```json
exchange: binance
markets: AVAX-USDT,AVAX-BNB,AVAX-BTC
token: AVAX
order_amount: 0.4
spread: 1%
target_base_pct: 50%
order_refresh_time: 10
order_refresh_tolerance_pct: 0.2
inventory_range_multiplier: 1.0
volatility_interval: 20
avg_volatility_period: 2
volatility_to_spread_multiplier: 1.0
```

This strategy lets you run multiple token pairs in one bot. The bot distributes the `token` balance to create three orders on both bid and ask. Ensure that your orders meet the minimum order size of the exchange for it to create orders on all pairs.

![](/assets/img/lm-status.png)

The bot will calculate the volatility based on the interval set. In this case, it is 20s. Then the `avg_volatility_period` will calculate the intervals and replace the spread if the value is higher than the current spread. The new spread also depends on the `volatility_to_spread_multiplier` in this case is set to 1.

![](/assets/img/volatility_interval.png)

The spread for was widened in the image below because the volatility % was higher than the spread set because of the dynamic spread adjustment on market volatility.

![](/assets/img/volatility_spread.png)
