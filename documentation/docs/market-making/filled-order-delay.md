# Filled Order Delay

By default, Hummingbot places orders as soon as there are no active orders; i.e., Hummingbot immediately places a new order to replace a filled order. If there is a sustained movement in the market in any one direction for some time, there is a risk of continued trading in that direction: For example, continuing to buy and accumulate base tokens in the case of a prolonged downward move or continuing to sell in the case of a prolonged upward move.

The `filled_order_delay` parameter allows for a delay when placing a new order in the event of an order being filled, which will help mitigate the above scenarios.

## `filled_order_delay`

How long to wait before placing the next set of orders in case at least one of your orders gets filled.

For example, with a filled_order_delay = 300 when an order created by the bot is filled, the next pair of orders will only be created 300 seconds later.

** Prompt: **

```json
How long do you want to wait before placing the next order if your order gets filled (in seconds)?
>>> 300
```

## How it works

This helps to manage periods when prices are trending. For example, in the diagram below, in a case when prices are trending down, bid orders keep getting filled once orders are refreshed.

![](/assets/img/Filled-order-delay.png)

If this is repeated and continues to go on, the market maker could quickly end up accumulating large amounts of the asset within a matter of just a few order refresh cycles. In the example above, the trader has bought assets 5 times.

By introducing a delay between filled orders and placing new orders, this spaces out orders and dampens the potential accumulation of assets, allowing for some time for price trends to stabilize.

![](/assets/img/filled_order-delay-enabled.png)

You can see above, since the bid order in period 1 was filled, the bot didn’t place orders in periods 2, 3, and 4. So in this downward price trend, the bot only bought twice (periods 1 and 5) whereas when filled order delay was not enabled, the bot would have bought in all five periods.

As an example, our buy and sell orders are created at exactly `00:00:00`.

```
00:00:00 - (BTCUSDT) Creating 1 bid order at ['0.005 BTC, 9026.63 USDT']
00:00:00 - (BTCUSDT) Creating 1 ask order at ['0.005 BTC, 9072.081 USDT']
```

```
Markets:
  Exchange   Market  Best Bid Price  Best Ask Price  Mid Price
   binance  BTCUSDT         9071.79         9072.13    9071.9

Assets:
                            BTC     USDT
   Total Balance           0.05      500
   Available Balance      0.045 454.8668
   Current Value (USDT) 453.598      500
   Current %              47.6%    52.4%

Orders:
   Level  Type    Price Spread Amount (Orig)  Amount (Adj)       Age
       1  sell 9072.081  0.01%         0.005         0.005  00:00:01
       1   buy  9026.63  0.50%         0.005         0.005  00:00:01
```

When one order gets filled, it will wait for `filled_order_delay` before creating new sets of orders. The remaining order will be cancelled based on order refresh time. See examples in the next sections.

## Filled order delay with shorter order refresh time

```json
- order_refresh_time: 30.0
- filled_order_delay: 60.0
```

Let's say our sell order was filled at `00:00:10`.

```
00:00:10 - (BTCUSDT) Maker sell order of 0.0050000 BTC filled.
00:00:10 - (BTCUSDT) Maker sell order (0.0050000 BTC @ 9072.0810000000 USDT)
                     has been completely filled.
```

The unfilled order will be cancelled after 30 seconds from the time it was created. Which means from `00:00:30` until `00:01:09` you won't see any active orders.

```
00:00:30 - (BTCUSDT) Cancelling the buy limit order
```

```
Markets:
  Exchange   Market  Best Bid Price  Best Ask Price  Mid Price
   binance  BTCUSDT         9073.91         9074.37    9074.14

Assets:
                             BTC     USDT
   Total Balance           0.045 545.3783
   Available Balance       0.045 545.3783
   Current Value (USDT) 408.3363 545.3783
   Current %               42.8%    57.2%

No active maker orders.
```

```
00:01:10 - (BTCUSDT) Creating 1 bid order at ['0.005 BTC, 9047.709 USDT']
00:01:10 - (BTCUSDT) Creating 1 ask order at ['0.005 BTC, 9093.266 USDT']
```

## Filled order delay with longer order refresh time

```json
- order_refresh_time: 120.0
- filled_order_delay: 60.0
```

Using the same scenario, our sell order was filled at `00:00:10` and leaves the buy order active.

```
00:00:10 - (BTCUSDT) Maker sell order of 0.0050000 BTC filled.
00:00:10 - (BTCUSDT) Maker sell order (0.0050000 BTC @ 9072.0810000000 USDT)
                     has been completely filled.
```

```
Markets:
  Exchange   Market  Best Bid Price  Best Ask Price  Mid Price
   binance  BTCUSDT          9071.8         9072.83   9072.315

Assets:
                             BTC     USDT
   Total Balance           0.045 545.3604
   Available Balance       0.045 500.2273
   Current Value (USDT) 408.2542 545.3604
   Current %               42.8%    57.2%

Orders:
   Level Type   Price Spread Amount (Orig)  Amount (Adj)       Age
       1  buy 9026.63  0.50%         0.005         0.005  00:00:11
```

Notice the timestamps. Since the refresh time is longer than the filled order delay, the unfilled order will remain active until it's time to create new sets of orders.

```
00:01:09 - (BTCUSDT) Cancelling the buy limit order
```

```
00:01:10 - (BTCUSDT) Creating 1 bid order at ['0.005 BTC, 9047.709 USDT']
00:01:10 - (BTCUSDT) Creating 1 ask order at ['0.005 BTC, 9093.266 USDT']
```
