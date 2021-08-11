Automatically stops the bot when it reaches a certain performance threshold, which can be either positive or negative. This feature uses the same performance calculation methodology as the [history](/operation/command-ref#history) command.

```
Would you like to enable the kill switch? (Yes/No) >>>
At what profit/loss rate would you like the bot to stop? (e.g. -5 equals 5 percent loss) >>>
```

You can always reconfigure this feature in two ways:

1. Inside Hummingbot run command `config kill_switch_enabled` and/or `config kill_switch_rate`.
2. Edit `conf_global.yml` file using a text editor.

Note that when the market prices changes, so does the bot's performance and may trigger the kill switch. For example, we executed 13 trades and our performance are shown below.

```json
- kill_switch_enabled: True
- kill_switch_rate: -0.3
```

```
Inventory:
      Market Asset  Starting   Current  Net Delta Trade Delta
  0  binance   ETH   10.0000   11.0000     1.0000      3.0000
  1  binance  USDT  500.0000  297.1580  -202.8420   -610.6340

Markets:
      Market     Pair Start Price       End Price  Trades Trade Value Delta
  0  binance  ETHUSDT     203.913  202.7150000000      13  -2.48900000 USDT

Performance:
  Started: 2020-05-26 10:28:03
  Duration: 0 days 00:07:06
  Total Trade Value Delta: -2.489 USDT
  Return %: -0.0985 %
```

After a while, the end price changed from 202.715 to 200.54 and so did our bot's performance even without making more trades. Since `kill_switch_rate` is set to `-0.3` this will stop the strategy.

```
Inventory:
      Market Asset  Starting   Current  Net Delta Trade Delta
  0  binance   ETH   10.0000   11.0000     1.0000      3.0000
  1  binance  USDT  500.0000  297.1580  -202.8420   -610.6340

Markets:
      Market     Pair Start Price       End Price  Trades Trade Value Delta
  0  binance  ETHUSDT     203.913  200.5400000000      13  -9.01400000 USDT

Performance:
  Started: 2020-05-26 10:28:03
  Duration: 0 days 02:09:13
  Total Trade Value Delta: -9.014 USDT
  Return %: -0.3598 %
```

```
[Kill switch triggered]
Current profitability is -0.003550034854458‬. Stopping the bot...
kill_switch - Kill switch threshold reached. Stopping the bot...
```
