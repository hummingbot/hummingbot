
Displays the top 5 bid/ask prices and volume of the current market, similar to how they're displayed in the exchange's order book.

```
>>>  order_book
  market: binance ETHUSDT

     bid_price  bid_volume  ask_price  ask_volume
        395.87     0.73244     395.89    34.37802
        395.86           7      395.9      10.786
        395.85    71.36763     395.91        0.19
        395.84      12.786     395.92     2.02141
        395.83     16.5706     395.93     3.29861
```

!!! Note
    This command will only work while a strategy is running.

Run `order_book --lines [value]` to specify the number of lines displayed.

```
>>>  order_book --lines 15
  market: binance ETHUSDT

     bid_price  bid_volume  ask_price  ask_volume
        395.91           6     395.93          30
         395.9     0.02764     395.94      10.786
        395.89       8.292     395.95     0.11719
        395.87    25.13292     395.96     8.53205
        395.86    61.26264     395.97      0.0007
        395.84    12.40548     395.98     7.52538
        395.83     20.7474     395.99     8.61834
        395.82          11        396    13.53414
        395.81     8.61536     396.02    12.92161
         395.8    60.38759     396.03     6.26138
        395.79     25.5767     396.04    21.61688
        395.78    31.94231     396.05    44.45931
        395.77    41.51229     396.06     0.19829
        395.76    24.17199     396.07    12.26197
        395.75      2.9788     396.08     1.21638
```

By default, the `order_book` command shows only the maker market in cross-exchange strategy or primary market when using arbitrage.

Optional arguments `--exchange` and `--market` allows you to check the order book of the taker market or secondary market.

Sample usage:

```
>>>  order_book --exchange kucoin --market ETH-USDT
  market: kucoin ETH-USDT

     bid_price  bid_volume  ask_price  ask_volume
         395.8        1.07     395.81        2.02
        395.79    22.95406     395.82   0.0505293
        395.77    7.668467     395.84    0.554996
        395.75        0.05     395.85    3.644207
         395.7           1     395.86       1.825
```