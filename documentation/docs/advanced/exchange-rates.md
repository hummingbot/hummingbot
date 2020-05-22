# Exchange Rates

When you run strategies on multiple exchanges, there may be instances where you need to utilize an **exchange rate** to convert between assets.

In particular, you may need to convert the value of one stablecoin to another when you use different stablecoins in multi-legged strategies like [cross-exchange market making](/strategies/cross-exchange-market-making) and [arbitrage](/strategies/arbitrage).

For example, if you make a market in the ==WETH/DAI== pair on a decentralized exchange, you may want to hedge filled orders using the ==ETH/USD== pair on Coinbase or the ==ETH/USDT== pair on Binance. Using exchange rates for USDT and DAI against USD allows Hummingbot to take into account differences in prices between these different stablecoins.

## Exchange Rate Class

To perform these conversions, Hummingbot includes an exchange rate class in `conf_global.yml`, which is located in the `/conf` directory. Here, you can either set a fixed exchange rate or provide a price feed API for Hummingbot to dynamically set the exchange rates in real-time.

### Default Configuration

In the file `conf/conf_global.yml` you will find the following listed:
```
exchange_rate_conversion:
- - DAI
  - 1.0
  - coin_gecko_api
- - USDT
  - 1.0
  - coin_gecko_api
- - USDC
  - 1.0
  - coin_gecko_api
- - TUSD
  - 1.0
  - coin_gecko_api
```
By default, Hummingbot uses the [CoinGecko API](https://www.coingecko.com/en/api) to set the USD exchange rate for the stablecoins listed above.

When you run Hummingbot using DAI and/or USDT, the exchange rates are displayed in the client window when running the `status` command:

![Exchange rate default](/assets/img/exchange-rate-default-new.png)

### Creating Custom Configurations

Say for instance that we modify the exchange rates class in `conf/conf_global.yml` to be the following:

```
exchange_rate_conversion:
- - DAI
  - 0.97
  - OVERRIDE
- - USDT
  - 1.0
  - OVERRIDE
- - USDC
  - 1.0
  - coin_gecko_api
- - TUSD
  - 1.0
  - coin_gecko_api
- - PAX
  - 1.0
  - coin_gecko_api
```

In the example above, 1 DAI is assumed to equal $0.97 USD, and 1 USDT is assumed to equal $1.00. We set a **fixed exchange rate** by replacing `coin_gecko_api` with `OVERRIDE` or `manual` and setting the desired exchange rate.

You can also add new crypto-assets. As shown in the exchange rate class above, PAX has been added which allows Hummingbot to use the PAX/USD exchange rate from CoinGecko.

You can see these custom exchange rates in the `status` command:
![Exchange rate custom](/assets/img/exchange-rate-custom-new.png)
