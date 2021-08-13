# Perpetual Market Making

!!! info
      This strategy only works with [Binance Futures](https://docs.hummingbot.io/derivative-connectors/binance-futures/), [Perpetual Finance (BETA)](https://docs.hummingbot.io/protocol-connectors/perp-fi/) & [dYdX Perpetual(BETA)](https://docs.hummingbot.io/spot-connectors/dydx/)

## How it works

Perpetual market making allows Hummingbot users to market make on supported derivatives exchanges. In addition, position management features are introduced to configure the bot further to make managing positions easier and remove the need to interact with the derivative exchange manually.

Like pure market making strategy, it keeps placing limit buy and sell orders on the order book and waits for other participants (takers) to fill its orders.

In this document, we will explain how the strategy works by dividing it into three behaviors:

1. [Creating orders to open a position](#creating-orders-to-open-a-position)
2. [Opening positions after a filled order event](#opening-positions-after-a-filled-order-event)
3. [Creating orders to close a position](#creating-orders-to-close-a-position)

!!! tip
      Users can test how this strategy works without risking real funds by connecting their Binance Futures Testnet account to Hummingbot.
      - [Create a free account with Binance Futures Testnet](https://testnet.binancefuture.com/en/register?source=futures)
      - [Creating Binance Futures Testnet API Keys](https://docs.hummingbot.io/derivative-connectors/binance-futures/#creating-binance-futures-testnet-api-keys)

!!! tip
      You can also watch the recording of our demo of the strategy in the link below:
      - "[Hummingbot Live - Perpetual Market Making Demo](https://www.youtube.com/watch?v=IclhZWtKiSA&t=2194s)

## Creating a basic strategy configuration

1. Make sure to connect to an exchange supported by Perpetual Market Making strategy
   - [How to use the `connect` command to connect your API keys](/operation/connect-exchange)
1. Run the `create` command and enter `perpetual_market_making` strategy
   ![](/assets/img/perp-mm-prompt-strategy.png)
1. Enter the name of the connector and the trading pair you want to use with this strategy
1. Enter how much leverage you want to use. Leverage allows you to open a position at a fraction of a cost. The higher the leverage, the higher the risk. Please manage accordingly.
   ![](/assets/img/perp-mm-prompt-leverage.png)
1. Select a `position_mode` from either [`One-way`](#one-way-mode) or [`Hedge`](#hedge-mode) mode. These are both explained further in their respective sections below.
   ![](/assets/img/perp-mm-prompt-position-mode.png)
1. Enter the bid and ask spreads from mid-price of your limit orders (for opening a position)
   ![](/assets/img/perp-mm-prompt-bid-spread.png)
   ![](/assets/img/perp-mm-prompt-ask-spread.png)
1. Enter how many seconds you want orders to refresh when not filled
   ![](/assets/img/perp-mm-prompt-order-refresh-time.png)
1. Enter the size of orders you want to place in the `order_amount` prompt
1. Select a `position_management` from either [`Profit_taking`](#profit-taking) or [`Trailing_stop`](#trailing-stop) value
   ![](/assets/img/perp-mm-prompt-position-management.png)
   - If you selected `Profit_taking`, enter the spreads of your profit taking orders to close a long or short position in `long_profit_taking_spread` `short_profit_taking_spread`
     ![](/assets/img/perp-mm-prompt-long-profit-taking-spread.png)
     ![](/assets/img/perp-mm-prompt-short-profit-taking-spread.png)
   - If you selected `Trailing_stop`, enter the spread when you want the bot to start trailing as `ts_activation_spread` and the exit price as `ts_callback_rate`
     ![](/assets/img/perp-mm-prompt-ts-activation-spread.png)
     ![](/assets/img/perp-mm-prompt-ts-callback-rate.png)
1. Enter the spread from the entry price to close a position with a stop-loss order
   ![](/assets/img/perp-mm-prompt-stop-loss.png)
1. Choose between limit or market order when `close_position_order_type` value for stop loss and trailing stop orders
   ![](/assets/img/perp-mm-prompt-close-position-order-type.png)
1. The strategy configuration file is saved in the Hummingbot folder
   - [Where are my configuration files saved?](https://hummingbot.zendesk.com/hc/en-us/articles/900005206343-Where-is-my-config-and-log-file-)

## Creating orders to open a position

Initially, limit buy and sell orders are created based on `bid_spread` and `ask_spread` settings. This determines the entry price of the position to be opened when these orders are filled.

**What happens if both my orders are not filled?**

If the orders are not filled when they reach `order_refresh_time`, they are canceled, and a new set of orders are created to ensure our orders are refreshed based on specified bid/ask spread.

With the exception of the `order_refresh_tolerance_pct` value, if the orders are within the tolerable change in the spread, then they are not canceled. A log message on the right pane will show “Not canceling active orders since the difference between the new order prices and current order prices is within order_refresh_tolerance_pct”.

![opening-orders-1](/assets/img/opening-orders-1.gif)

## Opening positions after a filled order event

The strategy uses the filled order’s price as the entry price of the position. Thus, the number of positions you can open depends on the `position_mode` selected.

**If one of my orders is filled, what happens to the opposite order that was not filled?**

In `One-way` mode, if an order is filled, the opposite order is canceled. For example, if your buy order is filled, it opens a LONG position, cancels the opening sell order, and creates a closing sell order.

In `Hedge` mode, if one order is filled, the opposite order is not canceled. For example, if your buy order is filled, it opens a LONG position and creates a closing sell order. The opening sell order initially created remains active, waiting to get filled to open a SHORT position simultaneously.

### One-way mode

In `One-way` mode, only one position can be opened i.e., you only have either a LONG or a SHORT position.

Sample scenario:

```
bid_spread: 0.01
ask_spread: 1.00
order_refresh_time: 10
position_mode: One-way
```

Using the sample configuration above, we will try to get our buy order only filled on purpose.

If the buy order is filled, then the opposite sell order is canceled, and a long position is opened. On the other hand, if your sell order is filled first, the opposite buy order is canceled and opens a short position.

### Hedge mode

In `Hedge` mode, two positions can be opened simultaneously i.e. you can have one LONG and one SHORT position.

Sample scenario:

```
bid_spread: 0.01
ask_spread: 0.05
order_refresh_time: 10
position_mode: Hedge
```

Using the sample configuration above, we will try to get our buy order filled first on purpose.

If the buy order is filled, a long position is opened and the opposite sell order is not cancelled. If the sell order eventually gets filled even with an open long position, a short position will be opened.

## Creating orders to close a position

Positions are closed in three different ways:

1. Profit taking orders are filled (for `Profit_taking` position management)
2. Market falls to or below the estimated exit price (for `Trailing_stop` position management)
3. Stop loss is triggered because profitability falls to or below the `stop_loss_spread` value

**Why is my bot not creating orders to close a position?**

The strategy includes a logic that it will not create these orders when the position's profitability is at a loss (PNL at negative value). In the sample screenshot below, you can see that we have an open long position but no profit taking orders because PNL (ROE%) is at a loss.

![closing-orders-1](/assets/img/closing-orders-1.png)

These are the logs in Hummingbot. Notice our position was opened at 03:52 when the buy order was filled but only created a profit taking sell order after 8 minutes when our PNL went up to a positive value.

![closing-orders-4](/assets/img/closing-orders-4.png)

![closing-orders-2](/assets/img/closing-orders-2.png)

![closing-orders-3](/assets/img/closing-orders-3.png)

### Profit taking

Hummingbot creates a sell order to close a long position and a buy order to close a short position. If these orders are filled, the position is closed.

Sample scenario:

```
position_management: Profit_taking
long_profit_taking_spread: 5
short_profit_taking_spread: 1
```

If the price of your filled buy order is 10,000 then it opens a long position with that entry price. If your `long_profit_taking_spread` is set to 5% it will create a profit taking sell order at 10,500.

If the price of your filled sell order is 10,000 it opens a short position. The bot will create a profit taking buy order at 9,900 because our `short_profit_taking_spread` is set to 1% value.

### Trailing stop

This position management allows users to maximize the profitability of a position. When an order is filled and a position is opened, it waits for PNL to reach the `ts_activation_spread` to start trailing. If this value is set to 0, the bot starts trailing immediately as soon as the order is filled.

Trailing is when Hummingbot monitors for the market’s peak price and determines your exit price based on `ts_callback_rate` value.

Sample scenario:

```
ts_activation_spread: 10
ts_callback_rate: 5
```

Let’s say your buy order is filled again at 10,000 and opens a long position. It waits for the best sell price to reach 11,000 (10% from the entry price) before the bot can start trailing by monitoring for the peak price. The market went down to 10,500 the next minute and went up again to 12,000. Our new peak price is now 12,000 and our exit price is 11,400 (5% callback rate).

When the market falls to or below 11,400 the bot will create a limit or market (depending on `close_position_order_type` value) sell order to close the position.

**Estimated exit price is Nill USDT**

Price `NILL` means the exit price is not profitable based on the current peak price.

![price-nill](/assets/img/price-nill.png)

### Stop loss

If the position’s profitability (PNL) is equal to or below the `stop_loss_spread`, the bot will create a limit or market order (depending on `close_positon_order_type` value) at the current mark price to close the position.

If there are outstanding limit orders, they are cancelled and replaced with a stop loss order.

## Using limit or market orders to close a position

Most of us are aware that submitting a market order instantly executes a trade by taking the best order in the order book while a limit order is an order that you place on the order book (taker) with a specific limit price, waiting for someone to fill that order therefore adding liquidity to the market.

Taker fees are typically higher than maker fees in most exchanges.

- [Fee Schedule of Binance Futures](https://www.binance.com/en/support/faq/360033544231)

For `close_position_order_type` parameter, some users use `LIMIT` order type for stop loss or trailing stop orders to close a position to take advantage of the maker fees, while some users use `MARKET` order type in case of network connectivity problems.

If you’re running the bot or strategy on a machine with poor network connection, chances are the order book prices will not be updated right away which could affect your limit order prices and your positions might be closed at the profitability you were not expecting.

Using market order type helps ensure that your positions are closed at mark price but paying higher fees.

## Basic parameters

Hummingbot prompts to enter the values for these parameters when creating the strategy.

| Parameter                    | Description                                                                                                                                                                                                  |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `derivative`                 | The derivative exchange where you want to trade                                                                                                                                                              |
| `market`                     | Token trading pair for the exchange e.g. BTC-USDT                                                                                                                                                            |
| `leverage`                   | How much the position is increased by                                                                                                                                                                        |
| `position_mode`              | Determines the number of positions that can be opened simultaneously. <br/><br/> Refer to [this section](#opening-positions-after-a-filled-order-event) for more information.                                |
| `bid_spread`                 | How far away from the price reference (by default, mid price) to place the buy order                                                                                                                         |
| `ask_spread`                 | How far away from the price reference (by default, mid price) to place the sell order                                                                                                                        |
| `order_refresh_time`         | Time (in seconds) to cancel active orders and place new ones with specified spreads.                                                                                                                         |
| `order_amount`               | The size or amount of your bid and ask orders                                                                                                                                                                |
| `position_management`        | Which position management feature to use. <br/> <br/> Current available options: <br/> [`Profit_taking`](#profit-taking) and [`Trailing_stop`](#trailing_stop)                                               |
| `long_profit_taking_spread`  | When using profit taking mode, the spread of profit taking order from the entry price to close a long position.                                                                                              |
| `short_profit_taking_spread` | When using profit taking mode, the spread of profit taking order from the entry price to close a short position.                                                                                             |
| `ts_activation_spread`       | Used with trailing stop position management, the profitability % of your position for the bot to start trailing.                                                                                             |
| `ts_callback_rate`           | Used with trailing stop position management, the callback % from the peak price to determine your position's exit price.                                                                                     |
| `stop_loss_spread`           | Triggers to close a position by creating a [stop loss](#stop-loss) order when profitability % falls below this value.                                                                                        |
| `close_position_order_type`  | The order type used (limit or market) when using trailing stop or when a stop loss is triggered. <br/><br/> Refer to [this section](#using-limit-or-market-orders-to-close-a-position) for more information. |

## Configure parameters on the fly 

Currently, only the following parameters can be reconfigured without stopping the bot. The changes will take effect in the next order refresh.

- bid_spread
- ask_spread
- order_amount
- order_levels
- order_level_spread
- filled_order_delay
