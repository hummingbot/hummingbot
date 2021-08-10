This feature allows users to test Hummingbot and simulate trading strategies without risking any actual assets. Enter the command `paper_trade` to enable this feature.

![papertrade ](/assets/img/paper_trade.gif)

!!! note
    Exchange APIs are not required to run the bot on paper_trade for Pure Market making, Cross Market Making and Liquidity Mining strategies.

## Enabling and Disabling

Paper trading mode can be enabled and disabled from the Hummingbot client by doing `paper_trade` or `config paper_trade_enabled`.

The top bar shows the status to indicate if paper trading mode is on or off.

![papertrade2 ](/assets/img/paper_trade_mode2.png)

Also shows a reminder that paper trade was enabled when doing a `status` or `history` command.

![papertrade3 ](/assets/img/paper_trade_warning.png)

!!! tip
In the event that the bot is running on paper trade and you disable it, you need to `stop` and `start` the bot to apply the changes. Make sure your Exchange APIs are connected as well when going live.

## Adding Paper Trade Balance

By default, the paper trade account has the following tokens and balances which you can see when you run the `balance paper` command.

```
>>>  balance paper
Paper account balances:
    Asset    Balance
      DAI  1000.0000
      ETH    10.0000
      ONE  1000.0000
     TUSD  1000.0000
     USDC  1000.0000
     USDQ  1000.0000
     USDT  1000.0000
     WETH    10.0000
      ZRX  1000.0000
```

When adding balances, specify the asset and balance you want by running this command `balance paper [asset] [amount]`.

For example, we want to add 0.5 BTC and check our paper account balance to confirm.

```
>>>  balance paper BTC 0.5
Paper balance for BTC token set to 0.5

>>>  balance paper
Paper account balances:
    Asset    Balance
      BTC     0.5000
      DAI  1000.0000
      ETH    10.0000
      ONE  1000.0000
     TUSD  1000.0000
     USDC  1000.0000
     USDQ  1000.0000
     USDT  1000.0000
     WETH    10.0000
      ZRX  1000.0000
```

Here is the list of our Supported Connectors that could run `paper_trade` as of version 0.38.0:
* AscendEx
* Binance
* Binance US
* Bitfinex
* Bittrex Global
* Coinbase Pro
* Huobi Global
* Kraken
* KuCoin
* Liquid
* OKEx
