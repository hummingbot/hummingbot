# Tips & Known Issues

## Trades may not be profitable at lower `min_profitability` values
Hummingbot does not yet take into account exchange fees and gas costs. In addition, for trading strategies that trade on two different markets, order book shifts may cause one or more legs of the trade to execute at a worse price that anticipated.

We are working on features that will bake fee/gas calculations in Hummingbot and enable users to more easily diagnose trade performance.

## Coinbase Pro: Market orders for USDC pairs don't work
Currently, market orders for USDC trading pairs on Coinbase Pro cannot yet be placed via API. 

This means that these pairs should not be used with the **arbitrage** strategy, nor as the `taker_market` in the **cross-exchange market making strategy**. Since USDC market orders will fail, the Coinbase Pro leg of the trade will not be executed.

## Edit the configuration files directly

You may find it easier to edit the configuration files rather than using Hummingbot's `config` command. The [configuration files](/configuration/#sample-config-files) are automatically created after the first time the user runs the `config` command.

## Use your Metamask Ethereum address

If you use the same Ethereum address for both Hummingbot and [Metamask](https://metamask.io), you can  navigate to a decentralized exchange's website and observe the orders created and trades filled by Hummingbot.

## Trading pair syntax differences

Hummingbot throws an error if the trading pair entered by the user isn't available on the exchange. However, each exchange may have different syntax for their trading pairs, and different trading pairs, by convention, may switch the base asset and the quote asset.

Below are some trading pairs and their equivalents on different exchanges:

* DDEX: `BAT-WETH`, `ZRX-WETH`, `WETH-DAI`
* Binance: `BATETH`, `ZRXETH`, `ETHUSDT`

!!! tip
    Symbols differ across exchanges for technical reasons, not just arbitrary exchange nomenclature preferences.  For example, ETH and BTC on a centralized exchange would correspond to WETH and WBTC on a decentralized exchange, with the "wrapped" versions of ETH and BTC existing to enable interoperability with the DEX.
