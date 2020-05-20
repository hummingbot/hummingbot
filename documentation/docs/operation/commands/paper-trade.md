
Toggle paper trade mode on and off. When paper trade mode is enabled, all orders are simulated and no real orders are placed.

This feature allows users to test Hummingbot and simulate trading strategies without risking any actual assets.

```
>>>  paper_trade

Enable paper trading mode (Yes/No) ? >>> Yes

New configuration saved:
paper_trade_enabled: True
```

## Enabling and Disabling

Paper trading mode can be enabled/disabled inside Hummingbot by doing `paper_trade` or `config paper_trade_enabled`.

Alternatively, you can edit the `conf_global.yml` file using a text editor and set `paper_trade_enabled:` value to `true` or `false`.

The top bar shows the status to indicate if paper trading mode is on or off.

![](/assets/img/paper_trade_mode2.png)

Also shows a reminder that paper trade was enabled when doing a `status` or `history` command.

![](/assets/img/paper_trade_warning.png)

## Account Balance

By default, the paper trade account has the following tokens and balances:

```
paper_trade_account_balance:
- - USDT
  - 1000
- - ONE
  - 1000
- - USDQ
  - 1000
- - TUSD
  - 1000
- - ETH
  - 10
- - WETH
  - 10
- - USDC
  - 1000
- - DAI
  - 1000
```


Paper trade assets can be added in two ways:

1. From the Hummingbot client run command `config paper_trade_account_balance` and enter values exactly as shown in the prompt.
![](/assets/img/paper_trade_balance.gif)
2. Edit `conf_global.yml` in the `/conf` or `hummingbot_conf` folder using a text editor. **Strictly follow the same format above**.

!!! warning
    When adding balances, make sure to exit and restart Hummingbot for the changes to take effect.


## Supported Connectors

- Binance
- Coinbase Pro
- Huobi
- Bamboo Relay
- Radar Relay
- Bittrex
- Dolomite
- Liquid
- KuCoin
- Kraken
