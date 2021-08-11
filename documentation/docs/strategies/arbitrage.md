# Arbitrage

## How it works

Arbitrage is described in [Strategies](overview), with a further discussion in the Hummingbot [white paper](https://hummingbot.io/hummingbot.pdf).

### Schematic

The diagram below illustrates how arbitrage works. The transaction involves two exchanges: **Exchange A** and **Exchange B**. Hummingbot monitors the prices on both exchanges and transacts when a profit opportunity arises.

An opportunity arises when Hummingbot can buy on one exchange at a lower price and sell on the other exchange at a higher price.

<small>
  <center>***Figure 1: Hummingbot completes an arbitrage trade***</center>
</small>

![Figure 1: Hummingbot completes an arbitrage trade](/assets/img/arbitrage.png)

## Prerequisites: Inventory

1. Like cross-exchange market making, you will need to hold inventory on two exchanges (a **primary** and **secondary** exchange) to trade and capture price differentials (i.e., buy low on one exchange, sell high on the other).
2. You will also need some Ethereum to pay gas for transactions on a DEX (if applicable).

## Basic parameters

The following walks through all the steps when running `create` command. These parameters are fields in Hummingbot configuration files (located in the `/conf` folder, e.g. `conf/conf_arb_[#].yml`).

### `primary_market`

Enter an exchange you would like to trade on.

** Prompt: **

```json
Enter your primary spot connector
>>> binance
```

### `secondary_market`

Enter another exchange you would like to trade on.

** Prompt: **

```json
Enter your secondary spot connector
>>> kucoin
```

### `primary_market_trading_pair`

Enter the token trading pair for the primary exchange.

** Prompt: **

```json
Enter the token trading pair you would like to trade on [primary_market]
>>>
```

### `secondary_market_trading_pair`

Enter the token trading pair for the secondary exchange.

** Prompt: **

```json
Enter the token trading pair you would like to trade on [secondary_market]
>>>
```

### `min_profitability`

Minimum profitability target required to execute trades.

** Prompt: **

```json
What is the minimum profitability for you to make a trade?
>>>
```

!!! note
    While running this strategy, `min_profitability` excludes the `transaction fees` when calculating profitability from your chosen exchanges.

### `use_oracle_conversion_rate`

Rate oracle conversion is used to compute the rate of a particular market pair using a collection of prices from either Binance or Coingecko.

If enabled, the bot will use a real-time conversion rate from the oracle when the trading pair symbols mismatch.
For example, if markets are set to trade for `LINK-USDT` and `LINK-USDC`, the bot will use the oracle conversion rate between `USDT` and `USDC`.

You can also edit it from `config_global.yml` to change the `rate_oracle_source`.

** Prompt: **

```json
Do you want to use rate oracle on unmatched trading pairs? (Yes/No)
>>>
```

!!! tip
    For autocomplete inputs during configuration, when going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.

## Advanced parameters

The following parameters are fields in Hummingbot configuration files (located in the `/conf` folder, e.g. `conf/conf_arb_[#].yml`).

### `secondary_to_primary_base_conversion_rate`

Specifies conversion rate for secondary quote asset value to primary quote asset value.

### `secondary_to_primary_quote_conversion_rate`

Specifies conversion rate for secondary quote asset value to primary quote asset value.

## Exchange rate conversion

From past versions of Hummingbot, it uses [CoinGecko](https://www.coingecko.com/en/api) and [CoinCap](https://docs.coincap.io/?version=latest) public APIs to fetch asset prices. However, this dependency caused issues for users when those APIs were unavailable. Therefore, starting on version [0.28.0](/release-notes/0.28.0/#removed-dependency-on-external-data-feeds), Hummingbot uses exchange order books to perform necessary conversions rather than data feeds.

When you run strategies on multiple exchanges, there may be instances where you need to utilize an exchange rate to convert between assets.

In particular, you may need to convert the value of one stable coin to another when you use different stablecoins in a multi-legged strategy like [arbitrage](/strategies/arbitrage/).

For example, if you make a market in the WETH/DAI pair on a decentralized exchange, you may want to hedge filled orders using the ETH-USDT pair on Binance. Using exchange rates for USDT and DAI against ETH allows Hummingbot to take into account differences in prices.

```
maker_market: bamboo_relay
taker_market: binance
maker_market_trading_pair: WETH-DAI
taker_market_trading_pair: ETH-USDT
secondary_to_primary_base_conversion_rate: 1
secondary_to_primary_quote_conversion_rate: 1
```

By default, secondary to primary base conversion rate and secondary to primary quote conversion rate value are both `1`.

Our maker base asset is WETH and taker is ETH. 1 WETH is worth 0.99 ETH (1 / 0.99) so we will set the `secondary_to_primary_base_conversion_rate` value to 1.01.

While our maker quote asset is DAI, the taker is USDT, and 1 DAI is worth 1.01 USDT (1 / 1.01). Similar to the calculation we did for the base asset. In this case, we will set the `secondary_to_primary_quote_conversion_rate` to 0.99.

To configure a parameter value without going through the prompts, input command as `config [ key ] [ value ]`. These can be reconfigured without stopping the bot. However, it will only take effect after restarting the strategy.

```
config secondary_to_primary_base_conversion_rate: 1.01
config secondary_to_primary_quote_conversion_rate: 0.99
```
