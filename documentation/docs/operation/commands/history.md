
See the past performance of the current bot.

```
>>>  history

  Recent trades:
        symbol      price  amount order_type  side   market            timestamp  fee_percent flat_fee / gas
    0   ETHBTC 0.02553374       1      limit   buy  binance  2020-04-23 16:17:58         0.01          None
    1   ETHBTC 0.02553974       1      limit   buy  binance  2020-04-23 16:19:02         0.01          None
    2   ETHBTC 0.02554026       1      limit  sell  binance  2020-04-23 16:19:21         0.01          None
    3   ETHBTC 0.02553724       1      limit   buy  binance  2020-04-23 16:20:32         0.01          None
    4   ETHBTC 0.02553776       1      limit  sell  binance  2020-04-23 16:20:40         0.01          None
    5   ETHBTC 0.02553974       1      limit   buy  binance  2020-04-23 16:21:48         0.01          None
    6   ETHBTC 0.02553426       1      limit  sell  binance  2020-04-23 16:22:50         0.01          None
    7   ETHBTC 0.02553374       1      limit   buy  binance  2020-04-23 16:22:56         0.01          None
    8   ETHBTC 0.02552824       1      limit   buy  binance  2020-04-23 16:24:01         0.01          None
    9   ETHBTC 0.02551224       1      limit   buy  binance  2020-04-23 16:25:04         0.01          None
    10  ETHBTC 0.02551276       1      limit  sell  binance  2020-04-23 16:25:11         0.01          None
    11  ETHBTC 0.02552324       1      limit   buy  binance  2020-04-23 16:26:14         0.01          None
    12  ETHBTC 0.02552776       1      limit  sell  binance  2020-04-23 16:27:20         0.01          None
    13  ETHBTC 0.02553874       1      limit   buy  binance  2020-04-23 16:28:21         0.01          None
    14  ETHBTC 0.02553926       1      limit  sell  binance  2020-04-23 16:28:23         0.01          None
    15  ETHBTC 0.02554824       1      limit   buy  binance  2020-04-23 16:29:25         0.01          None

  Inventory:
        Market Asset Starting Current Net Delta Trade Delta
    0  binance   ETH   4.3725  8.3725    4.0000      4.0000
    1  binance   BTC   0.1274  0.0253   -0.1021     -0.1021

  Markets:
        Market    Pair Start Price   End Price  Trades Trade Value Delta
    0  binance  ETHBTC  0.02553374  0.02554850      16    0.00005116 BTC

  Performance:
    Started: 2020-04-23 16:15:21
    Duration: 00:14:20
    Total Trade Value Delta: 0.00005116 BTC
    Return %: 0.0214 %
```

## How it works

The `history` command in Hummingbot will show the current session's past trades, inventory, market trading pair performance, and return percentage.

**Return %** is calculated based on assets spent and acquired during trades, i.e. balance changes due to the inventory like deposits, withdrawals, and manual trades outside of Hummingbot do not affect the calculation.

As an example, let's say we are trading on ETH-DAI token pair and made 4 trades.

```
trade1: buy 1 ETH (acquired) for 100 DAI (spent)
trade2: sell 0.9 ETH (spent) for 100 DAI (acquired)
trade3: buy 0.1 ETH (acquired) for 10 DAI (spent)
trade4: sell 1 ETH (spent) for 100 DAI (acquired)
```

* Total `spent_amount` for DAI = 110 and total `acquired_amount` = 200
* Total `spent_amount` for ETH = 1.9 and total `acquired_amount` = 1.1

Final delta percentage for each asset is defined by `acquired_amount / spent_amount`.

* Performance for DAI = 200/110 = 81.8%
* Performance for ETH = 1.1/1.9 = 42.1%

Portfolio performance is also calculated as `total acquired / total spent` on both sides, converting base asset to quote asset using the latest price.

Assuming ETH price is 100 DAI, return percentage for ETH-DAI is 3.3%

![total-performance-sample](/assets/img/performance_total.png)

**Trade Value Delta** is calculated as the difference between the total assets acquired and total assets spent, specified in quote value.

In the sample below, we acquired 33.6754 USDT and spent 0.2001 ETH after executing 4 trades. Multiply the base asset 0.2001 ETH to the end price 168.205 to get its equivalent quote value 33.6578 USDT.

![](/assets/img/trade_value_delta.png)