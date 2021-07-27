# Check Bot and Market Status

## Check bot status

Run `status` command or CTRL+S to show the bot's current status. The output may differ depending on the running strategy, but generally, it shows the following information:

- Market(s) you're trading in
- Balance or inventory of trading pair assets
- Active or outstanding orders
- Error messages
- Exchange connection status
- Paper trading mode (when enabled)

## Get live bot status

The `status --live` command displays the real-time status of the bot.

![](/assets/img/status-live.gif)

!!! note
    Currently, this feature works on all strategies except Liquidity mining strategy.

## View market order book

By default, the `order_book` command displays the top 5 bid/ask prices and volume of the current market, similar to how they're displayed in the exchange's order book.

**Optional arguments**

| Command Argument | Description                                                  |
| ---------------- | ------------------------------------------------------------ |
| `--live`         | Continuously displays the order book in real-time            |
| `--lines`        | Number of lines to display                                   |
| `--exchange`     | Specifies the exchange when running a secondary exchange     |
| `--market`       | Specifies the trading pair when running a secondary exchange |

**Sample usage**

Run `order_book --live --lines 20` to show the top 20 bid/ask and volume in real-time.

![](/assets/img/orderbook-live-lines.gif)

## View market ticker prices

The `ticker` command displays the market prices, specifically the best bid, best ask, mid price, and last trade price.

![](/assets/img/ticker-command.png)

**Optional arguments**

| Command Argument | Description                                                  |
| ---------------- | ------------------------------------------------------------ |
| `--live`         | Displays the ticker in real-time                             |
| `--exchange`     | Specifies the exchange when running a secondary exchange     |
| `--market`       | Specifies the trading pair when running a secondary exchange |

## open_orders

Show all active open orders.

| Command Argument | Description                           |
| ---------------- | ------------------------------------- |
| `--full_report`  | Show full report with size comparison |

!!! note
    `open_orders` only works with Binance exchange connector.

## trades

Show trades

!!! note
    `trades` only works with Binance exchange connector. If your desired trading pair does not show any result on your hummingbot terminal when running the `trades` command, you can use the following command `trades --market [pair]`.

![img/trades_sample.png](/assets/img/trades_sample.png)

## pnl

Show profit and losses

| Command Argument       | Description                                      |
| ---------------------- | ------------------------------------------------ |
| `--days`               | How many days in the past (can be decimal value) |
| `--market`             | The market you want to see pnl                   |
| `--open_order_markets` | See pnl from current open order markets          |

!!! note
    `pnl` only works with Binance exchange connector. If your desired trading pair does not show any result on your hummingbot terminal when running the `pnl` command. You can edit the `conf_global.yml` file on your hummingbot folder and add the market pair that you're trading under the `binance_market` list. You can also add it on your hummingbot terminal by using `config binance_market`

![img/market_binance.png](/assets/img/market_binance.png)

## status

Get the market status of the current bot.

```
>>>  status

  Markets:
    Exchange  Market  Best Bid Price  Best Ask Price  Mid Price
     binance  ETHBTC        0.025521        0.025527   0.025524

  Assets:
                            ETH    BTC
     Total Balance       4.3725 0.1274
     Available Balance   3.3725 0.1021
     Current Value (BTC) 0.1116 0.1274
     Current %            46.7%  53.3%

  Orders:
     Level  Type      Price Spread  Amount (Orig)  Amount (Adj)       Age Hang
         1  sell  0.0257747  0.98%              1             1  00:00:02   no
         1   buy 0.02526431  1.02%              1             1  00:00:02   no



**Optional arguments**

| Command Argument            | Description                                                  |
| --------------------------- | ------------------------------------------------------------ |
| `-live`                     | Displays status in real time.                                |
```
