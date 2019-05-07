# Exchange rates

When you run strategies on multiple exchanges, there may be instances where you need to utilize an **exchange rate** to convert between assets. 

In particular, you may need to convert the value of one stablecoin to another when you use different stablecoins in multi-legged strategies like [cross-exchange market making](/strategies/cross-exchange-market-making) and [arbitrage](/strategies/arbitrage). 

For example, if you make a market in the ==WETH/DAI== pair on a decentralized exchange, you may want to hedge filled orders using the ==ETH/USD== pair on Coinbase or the ==ETH/USDT== pair on Binance. Using exchange rates for USDT and DAI against USD allows Hummingbot to take into account differences in prices between stablecoins.

## Exchange rate class
To performance these conversions, Hummingbot includes an exchange rate class in `conf_global.yml` in the `/conf` directory. Here, you can either set a fixed exchange rate or tell Hummingbot to use a price feed API to dynamically set the exchange rates in real-time.

### Example: default configuration
In the file `conf/conf_global.yml`:
```
exchange_rate_conversion:
- - DAI
  - 1.0
  - COINCAP_API
- - USDT
  - 1.0
  - COINCAP_API
- - USDC
  - 1.0
  - COINCAP_API
- - TUSD
  - 1.0
  - COINCAP_API
```
By default, Hummingbot uses the <a href="https://docs.coincap.io/" target="_blank">CoinCap API</a> to set the USD exchange rate for the stablecoins above.

When you run Hummingbot using either DAI and/or USDT, the exchange rates are displayed in the `status` command:
![Exchange rate default](/assets/img/exchange-rate-default.png)

### Example: custom configuration
In the file `conf/conf_global.yml`:
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
  - COINCAP_API
- - TUSD
  - 1.0
  - COINCAP_API
- - PAX
  - 1.0
  - COINCAP_API
```

To set a fixed exchange rate, replace `COINCAP_API` with `OVERRIDE` and set the fixed exchange rate. In the example  above, 1 DAI is assumed to equal $0.97 USD, and 1 USDT is assumed to equal $1.00.

You can also add new crypto-assets. In the example above, the addition of PAX allows Hummingbot to use the PAX/USD exchange rate from CoinCap.

You can see these custom exchange rates in the `status` command:
![Exchange rate custom](/assets/img/exchange-rate-custom.png)

