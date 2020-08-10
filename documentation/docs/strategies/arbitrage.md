# Arbitrage

## How it Works

Arbitrage is described in [Strategies](/strategies/), with a further discussion in the Hummingbot [white paper](https://hummingbot.io/hummingbot.pdf).

### Schematic

The diagram below illustrates how arbitrage works.  The transaction involves two exchanges: **Exchange A** and **Exchange B**. Hummingbot monitors the prices on both exchanges and transacts when a profit opportunity arises.

An opportunity arises when Hummingbot can buy on one exchange at a lower price and sell on the other exchange at a higher price.

<small><center>***Figure 1: Hummingbot completes an arbitrage trade***</center></small>

![Figure 1: Hummingbot completes an arbitrage trade](/assets/img/arbitrage.png)

## Prerequisites: Inventory

1. Similar to cross-exchange market making, you will need to hold inventory on two exchanges (a **primary** and **secondary** exchange), in order to be able to trade and capture price differentials (i.e. buy low on one exchange, sell high on the other).
2. You will also need some Ethereum to pay gas for transactions on a DEX (if applicable).

## Configuration Parameters and Walkthrough

The following walks through all the steps when running `create` command. These parameters are fields in Hummingbot configuration files (located in the `/conf` folder, e.g. `conf/conf_arb_[#].yml`).

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **primary_market** | `Enter your primary exchange name` | Enter an exchange you would like to trade on. |
| **secondary_market** | `Enter your secondary exchange name` | Enter another exchange you would like to trade on. |
| **primary_market_trading_pair** | `Enter the token trading pair you would like to trade on [primary_market]` | Enter the token trading pair for the primary exchange. |
| **secondary_market_trading_pair** | `Enter the token trading pair you would like to trade on [secondary_market]` | Enter the token trading pair for the secondary exchange. |
| **min_profitability** | `What is the minimum profitability for you to make a trade?` | Minimum profitability target required to execute trades. |

!!! tip "Tip: Autocomplete Inputs during Configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.

## Advanced Parameters

### Exchange Rate Conversion

From past versions of Hummingbot it uses [CoinGecko](https://www.coingecko.com/en/api) and [CoinCap](https://docs.coincap.io/?version=latest) public APIs to fetch asset prices. However, this dependency caused issues for users when those APIs were unavailable. Starting on version [0.28.0](/release-notes/0.28.0/#removed-dependency-on-external-data-feeds), Hummingbot uses exchange order books to perform necessary conversions rather than data feeds.

When you run strategies on multiple exchanges, there may be instances where you need to utilize an exchange rate to convert between assets.

In particular, you may need to convert the value of one stablecoin to another when you use different stablecoins in multi-legged strategy like [arbitrage](/strategies/arbitrage/).

For example, if you make a market in the WETH/DAI pair on a decentralized exchange, you may want to hedge filled orders using the ETH-USDT pair on Binance. Using exchange rates for USDT and DAI against ETH allows Hummingbot to take into account differences in prices.


```
maker_market: bamboo_relay
taker_market: binance
maker_market_trading_pair: WETH-DAI
taker_market_trading_pair: ETH-USDT
secondary_to_primary_base_conversion_rate: 1
secondary_to_primary_quote_conversion_rate: 1
```


By default secondary to primary base conversion rate and secondary to primary quote conversion rate value are both `1`. 

Our maker base asset is WETH and taker is ETH. 1 WETH is worth 0.99 ETH (1 / 0.99) so we will set the `secondary_to_primary_base_conversion_rate` value to 1.01.

While our maker quote asset is DAI, taker is USDT and 1 DAI is worth 1.01 USDT (1 / 1.01). similar to the calculation we did for the base asset. In this case, we will set the `secondary_to_primary_quote_conversion_rate` to 0.99.

To configure a parameter value without going through the prompts, input command as `config [ key ] [ value ]`. These can be reconfigured without stopping the bot however, it will only take effect after restarting the strategy. 


```
config secondary_to_primary_base_conversion_rate: 1.01
config secondary_to_primary_quote_conversion_rate: 0.99
```


The following parameters are fields in Hummingbot configuration files (located in the `/conf` folder, e.g. `conf/conf_arb_[#].yml`).

| Term | Definition |
|------|------------|
| **secondary_to_primary_base_conversion_rate** | Specifies conversion rate for secondary quote asset value to primary quote asset value.
| **secondary_to_primary_quote_conversion_rate** | Specifies conversion rate for secondary quote asset value to primary quote asset value.