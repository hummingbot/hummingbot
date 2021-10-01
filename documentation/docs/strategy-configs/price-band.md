# Price Band

**Updated as of `v0.27.0`**

This feature allows you to set a price band within which your bot places both buy and sell orders normally.

## `price_ceiling`

Place only sell orders when mid price goes above this price.

** Prompt: **

```json
Enter the price point above which only sell orders will be placed
>>>
```

## `price_floor`

Place only buy orders when mid price falls below this price.

** Prompt: **

```json
Enter the price below which only buy orders will be placed
>>>
```

## How it works

`price_ceiling` and `price_floor` are two optional parameters that you can set. By default, these parameters have a value of -1, which means that they are not used.

Type `config price_ceiling` and `config price_floor` to set values for these parameters. If the mid price exceeds `price_ceiling`, your bot only places sell orders. If the price falls below `price_floor`, your bot only places buy orders.

Note that the `price_floor` cannot be greater than the `price_ceiling`.

## Sample configurations

```json
- order_refresh_time: 30
- order_refresh_tolerance_pct: 1%
- price_ceiling: 9750
- price_floor: 9730
```

With this configuration, Hummingbot will create both buy and sell orders if the mid price is between 9750 and 9730.

```
Markets:
  Exchange   Market  Best Bid Price  Best Ask Price  Mid Price
   binance  BTCUSDT         9745.02         9746.77   9745.895

Assets:
                            BTC    USDT
   Total Balance         0.0076 74.7486
   Available Balance     0.0046 46.1164
   Current Value (USDT) 73.8615 74.7486
   Current %              49.7%   50.3%

Orders:
   Level  Type   Price Spread Amount (Orig)  Amount (Adj)       Age
       1  sell 9933.62  1.93%         0.003         0.003  00:00:00
       1   buy 9544.06  2.07%         0.003         0.003  00:00:00
```

Since the mid price went above `price_ceiling` of 9750, the bot only created a sell order.

```
Markets:
  Exchange   Market  Best Bid Price  Best Ask Price  Mid Price
   binance  BTCUSDT         9754.86         9754.87   9754.865

Assets:
                            BTC    USDT
   Total Balance         0.0076 74.7486
   Available Balance     0.0046 46.0582
   Current Value (USDT) 73.9295 74.7486
   Current %              49.7%   50.3%

Orders:
   Level  Type   Price Spread Amount (Orig)  Amount (Adj)       Age
       1  sell  9953.8  2.04%         0.003         0.003  00:00:25
```

And when the mid price went down below the `price_floor` of 9730, Hummingbot created a buy order only.

```
Markets:
  Exchange   Market  Best Bid Price  Best Ask Price  Mid Price
   binance  BTCUSDT         9727.17         9727.26   9727.215

Assets:
                            BTC    USDT
   Total Balance         0.0076 74.7486
   Available Balance     0.0076 46.1469
   Current Value (USDT) 73.7199 74.7486
   Current %              49.7%   50.3%

Orders:
   Level Type   Price Spread Amount (Orig)  Amount (Adj)       Age
       1  buy 9533.89  1.99%         0.003         0.003  00:00:01
```

## Price band with order refresh tolerance

When it's time to refresh orders, the price band will take priority over the tolerable change in spreads.

## Price band with external pricing source

If `price_source` is enabled then the mid price reference point will be the external mid price.
