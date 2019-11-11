# Performance Analysis

The `history` command in Hummingbot will show the current session's past trades, inventory, market trading pair performance, and portfolio performance. Profit percentage is calculated based on assets spent and acquired during trades, i.e. balance changes due to the inventory like deposits, withdrawals, and manual trades outside of Hummingbot do not affect the calculation.

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

Assuming ETH price is 100 DAI, performance portfolio for ETH-DAI is 3.3%

![total-performance-sample](/assets/img/performance_total.png)
