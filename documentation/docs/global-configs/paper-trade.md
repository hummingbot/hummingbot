This feature allows users to test Hummingbot and simulate trading strategies without risking any actual assets.

!!! note
    Exchange APIs are not required to run the bot on paper_trade for Pure Market making, Cross Exchange Market Making and Avellaneda Market Making. `paper_trade` is only allowed on exchanges Binance, Kucoin, AscendEX, and Gate io.

## Enabling and Disabling

Paper trading can be enabled when creating a strategy and choosing an exchange when prompted `Enter your maker spot connector` during the creation of the strategy.

![papertrade1](/assets/img/binance_papertrade.png)

Alternatively, you can enable paper trading by inputting `config exchange` then choose the exchange that supports paper trade. 

![papertrade2](/assets/img/config_exchange.png)

To choose a different connector and go live, simply choose the exchange name without the `paper_trade` suffix then do the command `stop` and `start` so the changes will reflect on your configuration.

![papertrade3](/assets/img/papertrade_binance.png)


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

