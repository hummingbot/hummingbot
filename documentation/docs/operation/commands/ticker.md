
Displays market ticker prices such as best bid, best ask, mid price and last trade price. By default, it runs the output 10 times with 1 second in between intervals.

When optional arguments are not used i.e. running `ticker` alone displays the output from the **maker market** of a cross-exchange strategy or **primary market** when using arbitrage.

!!! Note
    This command will only work while a strategy is running.

## Optional arguments

| Command Argument | Description |
| -------- | ----------- |
| `--repeat` | To specify the number of times the output quote is displayed
| `--exchange` | The specific exchange of the market
| `--market` | The market trading pair of the order book


## Sample usage

When running a cross-exchange or arbitrage strategy, you can specify which exchange and market you can display.

```
>>>  ticker --repeat 3 --exchange binance --market ETH-USDT

   Best Bid  Best Ask  Mid Price  Last Trade
   351.41    351.42    351.415      351.42

   Best Bid  Best Ask  Mid Price  Last Trade
   351.41    351.42    351.415      351.42

   Best Bid  Best Ask  Mid Price  Last Trade
    351.4    351.41    351.405      351.41
```