# Exchange rates

When you run strategies on multiple exchanges, there may be instances where you need to utilize an **exchange rate** to convert between assets. 

In particular, you may need to convert the value of one stablecoin to another when you use different stablecoins in multi-legged strategies like [cross-exchange market making](/strategies/cross-exchange-market-making) and [arbitrage](/strategies/arbitrage).

## Exchange rate class
To performance these conversions, Hummingbot includes an exchange rate class in `conf_global.yml` in the `/conf` directory. Here, you can set USD exchange rates, either statically or dynamically via API) for various crypto-assets 

### Default configuration
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

### Custom configuration example
```
exchange_rate_conversion:
- - DAI
  - 0.97
  - DEFAULT
- - USDT
  - 1.0
  - DEFAULT
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