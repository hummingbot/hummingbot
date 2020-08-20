
Toggle paper trade mode on and off. When paper trade mode is enabled, all orders are simulated and no real orders are placed.

This feature allows users to test Hummingbot and simulate trading strategies without risking any actual assets. Enter the command `paper_trade` to enable this feature.

<!--
```
>>>  paper_trade

Enable paper trading mode (Yes/No) ? >>> Yes

New configuration saved:
paper_trade_enabled: True
```
-->
<img src="/assets/img/paper_trade.gif" alt="Enable Paper trade"  width="600" />

## Enabling and Disabling

Paper trading mode can be enabled/disabled inside Hummingbot by doing `paper_trade` or `config paper_trade_enabled`.

Alternatively, you can edit the `conf_global.yml` file using a text editor and set `paper_trade_enabled:` value to `true` or `false`.

* Locating your global configuration:<br />
    * Installed from source: `hummingbot/conf`<br />
    * Installed via Docker: `hummingbot_files/hummingbot_conf`<br />
        `hummingbot_files` is the default name of the parent directory. This can be different depending on the setup
        when the instance was created.<br />
    * Installed via Binary (Windows): `%localappdata%\hummingbot.io\Hummingbot\conf`<br />
    * Installed via Binary (MacOS): `~/Library/Application\ Support/Hummingbot/Conf`<br />

The top bar shows the status to indicate if paper trading mode is on or off.

![](/assets/img/paper_trade_mode2.png)

Also shows a reminder that paper trade was enabled when doing a `status` or `history` command.

![](/assets/img/paper_trade_warning.png)

## Account Balance

By default, the paper trade account has the following tokens and balances:

```
paper_trade_account_balance:
  BTC: 1
  USDT: 1000
  ONE: 1000
  USDQ: 1000
  TUSD: 1000
  ETH: 10
  WETH: 10
  USDC: 1000
  DAI: 1000
```

Paper trade assets can be added in two ways:

1. Run `balance paper [asset] [amount]`. See more information in [balance](/operation/commands/balance/#balance-paper-asset-amount) command.
2. Edit `conf_global.yml` in the `/conf` or `hummingbot_conf` folder using a text editor. **Strictly follow the same format above**.

!!! note
    When making changes to the global config file, make sure to exit and restart Hummingbot to take effect.


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