
See the past performance of the current bot.

```
>>>  history

  Recent trades:
                     Timestamp Exchange   Market   Order_type  Side     Price  Amount     Age
    Index
    1      2020-08-14 05:22:09  binance  ETHUSDT  limit_maker   buy  415.0885       1  00:00:23
    2      2020-08-14 05:23:14  binance  ETHUSDT  limit_maker   buy  415.3635       1  00:00:13
    3      2020-08-14 05:23:30  binance  ETHUSDT  limit_maker  sell  415.5504       1  00:00:14
    4      2020-08-14 05:24:31  binance  ETHUSDT  limit_maker   buy  415.8884       1  00:00:25

  Inventory:
         Market  Asset   Starting   Current  Net Delta  Trade Delta
    0   binance    ETH    10.0000   12.0000     2.0000       1.9970
    1   binance   USDT  1000.0000  169.2100  -830.7900    -831.2056

  Markets:
         Market     Pair  Start Price    End Price  Trades    Trade Value Delta
    0   binance  ETHUSDT     415.0885 415.99000000       4     -0.47352040 USDT

  Performance:
    Started: 2020-08-14 05:22:03
    Duration: 0 days 00:02:32
    Total Trade Value Delta: -0.4735204 USDT
    Return %: -0.0092 %
```

## How It Works

The `history` command in Hummingbot will show the current session's past trades, inventory, duration, market trading pair performance, and return percentage.


## Trade Value Delta

Total Trade Value Delta is calculated as the difference between the total assets acquired and total assets spent, specified in quote value.

$trade\_value\_delta = (acquired - spent)$

To get the quote value of base asset (acquired or spent), multiply the base value to end price.

```
Inventory:
       Market  Asset   Starting   Current  Net Delta  Trade Delta
  0   binance    ETH    10.0000   12.0000     2.0000       1.9970
  1   binance   USDT  1000.0000  169.2100  -830.7900    -831.2056

Markets:
       Market     Pair  Start Price    End Price  Trades   Trade Value Delta
  0   binance  ETHUSDT     415.0885 415.99000000       4    -0.47352040 USDT
```

After executing these trades we acquired **1.9970 ETH** equivalent to 830.73 USDT `(1.9970 ETH * 415.99)` and spent **831.2056 USDT** tokens.

```
Trade Value Delta = (830.73 USDT - 831.2056 USDT)
Trade Value Delta = -0.47357
```


## Return Percentage

Return is calculated based on assets spent and acquired during trades, i.e. balance changes due to the inventory like deposits, withdrawals, and manual trades outside of Hummingbot do not affect the calculation.

$Return\ \% = trade\_value\_delta / starting\_quote\_value$

```                                                                
Inventory:
       Market  Asset   Starting   Current  Net Delta Trade Delta
  0   binance    ETH    10.0000   12.0000     2.0000      1.9970
  1   binance   USDT  1000.0000  169.2100  -830.7900   -831.2056

Markets:
       Market     Pair  Start Price    End Price Trades  Trade Value Delta
  0   binance  ETHUSDT     415.0885 415.99000000      4   -0.47352040 USDT
```

Using the same example, get the starting quote value. Convert the starting ETH amount to USDT by multiplying to the start price and add the amount of quote assets. So we started with 4,150.89 USDT worth of ETH `(10 ETH * 415.0885)` and 1000 USDT total of **5,150.89 USDT**.

```
 Return%: -0.4735204 USDT / 5150.89 USDT
 Return %: -0.0092 %
```


## Net Delta

Net Delta is the difference of your starting balance and current balance i.e. it takes into calculation assets spent & acquired during trades, deposits and withdrawals. 

Trade Delta does not take into account deposits and withdrawals, only balance changes after executing trades in Hummingbot.

$net\_delta = starting\_balance - current\_balance$

```
Inventory:
       Market  Asset    Starting   Current  Net Delta Trade Delta
  0   binance    ETH     10.0000   12.0000     2.0000      1.9970
  1   binance   USDT   1000.0000  169.2100  -830.7900   -831.2056                                                                          
```

Using the same example, after executing these trades we can calculate Net Delta for base and quote assets, so Net Delta for base asset is **2.0000** because we started with `10.0000 ETH` and the current is `12.000 ETH`. Net Delta for quote asset is **-830.79 USDT** because we started with `1000.0000 USDT` and current is `169.21 USDT`, it means we lost **-830.79 USDT** on quote asset.

