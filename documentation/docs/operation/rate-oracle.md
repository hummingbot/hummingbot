This new feature provides real time, most up-to-date exchange rate on any given token or currency from a reliable and trustworthy data source.

!!! note
    Use rate oracle with the [cross exchange market making](/strategies/cross-exchange-market-making/) and [arbitrage](/strategies/arbitrage/) strategies.    

## Parameters

### `rate_oracle_source`

The source where you want to pull data from, it can either be Binance or Coingecko. Please take note that using Coingecko will have a 30-second delay due to their API rate limit.

```
What source do you want rate oracle to pull data from? (binance, coingecko)"
>>>
```

### `global_token`

This is a token which you can display other tokens' value in. Set the `global_token` according to your preferred token value.

```
What is your default display token? (e.g. USDT,USD,EUR)
>>>
```

### `global_token_symbol`

The symbol for the global token.

```
What is your default display token symbol? (e.g. $, €)
>>>
```

!!! tip Changing oracle sources
    If you happen to `start` the bot and produce the error `Oracle rate is not available`, or ff the `rate_oracle_source` fails to show any price reference on your pair, you may change the `oracle_source` by running `config rate_oracle_source` and switch between Binance or Coingecko.

![](/img/oracle-error.png)

## How it works

If you need to view the rate oracle conversion after the `balance`, `pnl`, `open_orders`, `trades`, and `status` command, set it manually in the `config_global.yml`.

To set the parameters for `rate_oracle_source`, `global_token` and `global_token_symbol`, run the `config` command.

Refer to the example below:

Change the default setting in `conf_global.yml` to GBP (Great Britain Pound). The conversion will show up when you run `balance` command.

![](/img/rate-oracle-global-config.png)

![](/img/rate-oracle-balance.png)

The conversion also shows up during the `status` command for the `liquidity_mining` strategy. Under the `Miner` section.

![](/img/oracle-status.png)

The conversion shows up when using the `pnl` command.

![ ](/assets/img/oracle-pnl.png)

The conversion also shows up when running the `trades` command.

![](/img/oracle-trades.png)

The conversion also works with the `open_orders` command.

![](/img/oracle-open-orders.png)
