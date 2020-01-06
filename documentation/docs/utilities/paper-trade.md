# Paper Trading Mode

This feature allows users to test Hummingbot and simulate trading strategies without risking any actual assets. An exchange account, Ethereum wallet and Ethereum address is also not required when using this feature.

## Enabling and Disabling

Paper trading mode can be enabled/disabled inside Hummingbot by doing `config paper_trade_enabled`. The command `paper_trade` can also be used but only before creating or importing a strategy config file.

Alternatively, you can edit the `conf_global.yml` file using a text editor and set `paper_trade_enabled:` value to `true` or `false`.

The top bar shows the status to indicate if paper trading mode is on or off.

![](/assets/img/paper_trade_mode.png)


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

Add more paper trade assets by editing `conf_global.yml` using a text editor. **Strictly follow the same format above**.

!!! warning
    When adding balances, make sure to exit and restart Hummingbot for the changes to take effect.


## Supported Connectors

- Binance
- Coinbase Pro
- Huobi
- DDEX
- Bamboo Relay
- Radar Relay
- Bittrex
- Dolomite
- Liquid

### Not yet supported

- IDEX

!!! note
    Make sure to set paper trade to `false` when running Discovery Strategy.

