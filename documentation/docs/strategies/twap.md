# TWAP Strategy

!!! bug
    Starting from version 0.41, we took out the existing TWAP strategy from the development branch into production. Please be advised of the [outstanding bugs](https://github.com/CoinAlpha/hummingbot/issues?q=is%3Aissue+is%3Aopen++in%3Atitle+TWAP+label%3Abug) which will be fixed in future releases.

## Creating the strategy

1. Make sure to connect to an exchange supported by the TWAP strategy
   - [How to use the `connect` command to connect your API keys](/operation/connect-exchange)
2. Run the `create` command and enter `twap` when prompted for the strategy you want to use
3. Enter the configuration of how you want the bot to behave by answering each prompt
4. To review your settings, run the `config` command
5. The strategy configuration file is saved in `logs/` or `hummingbot_logs` folder depending on how you installed Hummingbot

!!! tip
    If you already have an existing strategy config file created previously, follow the instructions on how to [import an existing strategy file](https://docs.hummingbot.io/operation/config-files/#import-an-existing-strategy-file).

## How it works

This strategy allows users to continuously create either buy or sell limit orders at a specified price at every time interval. To be more specific, the strategy performs the following:

1. It goes through preliminary checks on every cycle if it can break down the target amount into the number of desired orders and if there is enough balance
2. The `target_asset_amount` is the total amount of trades you want the strategy to execute. This target is broken down into smaller orders based on `order_step_size` value
3. Creates a one-sided limit order (buy or sell) based on `trade_side` at the specified `order_price`
4. Waits for `order_delay_time` value in seconds before creating another limit order (interval between orders)
5. Cancels any active order which has been outstanding more than the `cancel_order_wait_time` value in seconds
6. You can specify the duration how long the strategy should run by enabling `is_time_span_execution`, then set the `start_datetime` and `end_datetime` parameters
7. If the order step size is bigger than the pending amount or if the pending amount reaches 0, the strategy will stop creating additional orders

## Sample demo

!!! warning
    This demo is for instructional and educational purposes only. Any parameters used are purely for demo purposes only. We are not giving any legal, tax, financial, or investment advice. Every user is responsible for their use and configuration of Hummingbot.

<iframe width="733" height="474" src="https://www.loom.com/embed/8b36e590272c479fa0ccf69b011433e1" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>

## Basic parameters

Hummingbot prompts to enter the values for these parameters when creating the strategy.

| Parameter                | Description                                                              |
| ------------------------ | ------------------------------------------------------------------------ |
| `connector`              | The exchange where you want to trade                                     |
| `trading_pair`           | Token trading pair for the exchange e.g. BTC-USDT                        |
| `trade_side`             | Choose between creating buy or sell orders                               |
| `target_asset_amount`    | Total target amount to be traded                                         |
| `order_step_size`        | Size of each limit order to be created                                   |
| `order_price`            | Specifies the price of each limit order                                  |
| `is_time_span_execution` | Enables or disables the feature to run the strategy on a fixed time span |
| `start_datetime`         | Date and time to start the strategy                                      |
| `end_datetime`           | Date and time to stop the strategy                                       |
| `order_delay_time`       | The time interval (in seconds) in between orders                         |
| `cancel_order_wait_time` | How long you want to wait before canceling any unfilled order            |

## Troubleshooting

- If the strategy is not creating orders even with enough balance, your order may be below the exchange’s minimum trade size. Adjust the `order_step_size` and/or `order_price` accordingly
- If the start date/time and end date/time is not working, make sure that `is_time_span_execution` is enabled by setting it to `True`
- When `is_time_span_execution` is enabled, make sure `start_datetime` and `end_datetime` is configured. Otherwise, the strategy will not start
