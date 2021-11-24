This feature allows users to test Hummingbot and simulate trading strategies without risking any actual assets.

!!! note
    Exchange APIs are not required to run the bot on paper_trade for Pure Market making, Cross Exchange Market Making and Avellaneda Market Making. `paper_trade` is only allowed on exchanges Binance, Kucoin, AscendEX, and Gate io.

## Enabling and Disabling

Paper trading can be enabled by creating a strategy and choosing the exchange [exchange_name_paper_trade] when prompted.

![papertrade1](/assets/img/binance_papertrade.png)

Alternatively, you can change the exchange by inputting `config exchange` then choose the exchange that supports paper trade. 

![papertrade2](/assets/img/config_exchange.png)


To choose a different connector, choose the exchange name without the `paper_trade` suffix.

![papertrade3](/assets/img/papertrade_binance.png)

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

