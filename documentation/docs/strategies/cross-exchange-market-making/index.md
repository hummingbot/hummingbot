# Cross Exchange Market Making

## How it works
Also referred to as _liquidity mirroring_ or _exchange remarketing_, this strategy allows you to make a market (creates buy and sell orders) on one exchange, while hedging any filled trades on a second exchange.

The diagrams below illustrate how cross exchange market making works. The transaction involves two exchanges, a **taker exchange** and a **maker exchange**. Hummingbot uses the market levels available on the taker exchange to create the bid and ask orders (act as a market maker) on the maker exchange (_Figure 1_).

**Figure 1: Hummingbot acts as market maker on maker exchange**

![Figure 1: Hummingbot acts as a market maker on maker exchange](/assets/img/xemm-1.png)

**Buy order**: Hummingbot can sell the asset on the taker exchange for 99 (the best bid available); therefore, it places a buy order on the maker exchange at a lower value of 98.

**Sell order**: Hummingbot can buy the asset on the taker exchange for 101 (the best ask available), and therefore makes a sell order on the maker exchange for a higher price of 102.

**Figure 2: Hummingbot fills an order on the maker exchanges and hedges on the taker exchange**

![Figure 2: Hummingbot fills an order on the maker exchanges and hedges on the taker exchange](/assets/img/xemm-2.png)

If a buyer (_Buyer D_) fills Hummingbot's sell order on the maker exchange (_Figure 2_ ❶), Hummingbot immediately buys the asset on the taker exchange (_Figure 2_ ❷).

The end result: Hummingbot has sold the same asset at $102 (❶) and purchased it for $101 (❷), for a profit of $1.

## Basic parameters

The following walks through all the steps when running `create` command.

### `maker_market`

The exchange where the bot will place maker orders.

** Prompt: **

```json
Enter your maker spot connector
>>>
```

### `taker_market`

The exchange where the bot will place taker orders.

** Prompt: **

```json
Enter your taker spot connector
>>>
```

### `maker_market_trading_pair`

Trading pair for the maker exchange.

** Prompt: **

```json
Enter the token trading pair you would like to trade on maker market: [maker_market]
>>>
```

### `taker_market_trading_pair`

Trading pair for the taker exchange.

** Prompt: **

```json
Enter the token trading pair you would like to trade on taker market: [taker_market]
>>>
```

### `min_profitability`

Minimum required profitability for Hummingbot to place an order on the maker exchange.

** Prompt: **

```json
What is the minimum profitability for you to make a trade?
>>>
```

### `order_amount`

An amount expressed in base currency of maximum allowable order size.

** Prompt: **

```json
What is the amount of [base_asset] per order? (minimum [min_amount])
>>>
```

### `use_oracle_conversion_rate`

Rate oracle conversion is used to compute the rate of a certain market pair using a collection of prices from either Binance or Coingecko.

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

The following parameters are fields in Hummingbot configuration files (located in the `/conf` folder, e.g. `conf/conf_xemm_[#].yml`).

### `adjust_order_enabled`

If enabled, the strategy will place the order on top of the top bid and ask if it is more profitable to place it there. If disabled, the strategy will ignore the top of the maker order book for price calculations and only place the order based on taker price and min*profitability. Refer to the Adjusting orders and maker price calculations section above. \_Default value: True*

### `active_order_canceling`

If enabled, Hummingbot will cancel orders that become unprofitable based on the `min_profitability` threshold. If disabled, Hummingbot will allow any outstanding orders to expire unless `cancel_order_threshold` is reached.

### `cancel_order_threshold`

This parameter works when `active_order_canceling` is disabled. If the profitability of an order falls below this threshold, Hummingbot will cancel an existing order and place a new one, if possible. This allows the bot to cancel orders when paying gas to cancel (if applicable) is better than incurring the potential loss of the trade.

### `limit_order_min_expiration`

An amount in seconds, which is the minimum duration for any placed limit orders.

### `top_depth_tolerance`

An amount expressed in the base currency is used for getting the top bid and ask, ignoring dust orders on top of the order book.<br/><br/>_Example: If you have a top depth tolerance of `0.01 ETH`, then while calculating the top bid, you exclude orders starting from the top until the sum of orders excluded reaches `0.01 ETH`._

### `anti_hysteresis_duration`

An amount in seconds, which is the minimum amount of time interval between adjusting limit order prices.

### `order_size_taker_volume_factor`

Specifies the percentage of hedge-able volume on the taker side, which will be considered for calculating the market-making price.

### `order_size_taker_balance_factor`

Specifies the percentage of asset balance to be used for hedging the trade on the taker side.

### `order_size_portfolio_ratio_limit`

Specifies the ratio of total portfolio value on both maker and taker markets to calculate the order size if order_amount is not specified.

### `taker_to_maker_base_conversion_rate`

Specifies conversion rate for taker base asset value to maker base asset value.

### `taker_to_maker_quote_conversion_rate`

Specifies conversion rate for taker quote asset value to maker quote asset value.

## Exchange rate conversion

From past versions of Hummingbot, it uses [CoinGecko](https://www.coingecko.com/en/api) and [CoinCap](https://docs.coincap.io/?version=latest) public APIs to fetch asset prices. However, this dependency caused issues for users when those APIs were unavailable. Therefore, starting on version [0.28.0](/release-notes/0.28.0/#removed-dependency-on-external-data-feeds), Hummingbot uses exchange order books to perform necessary conversions rather than data feeds.

When you run strategies on multiple exchanges, there may be instances where you need to utilize an exchange rate to convert between assets.

In particular, you may need to convert the value of one stable coin to another when you use different stablecoins in multi-legged strategies like [cross-exchange market making](/strategies/cross-exchange-market-making/).

For example, if you make a market in the WETH/DAI pair on a decentralized exchange, you may want to hedge filled orders using the ETH-USDT pair on Binance. Using exchange rates for USDT and DAI against ETH allows Hummingbot to take into account differences in prices.

```
maker_market: bamboo_relay
taker_market: binance
maker_market_trading_pair: WETH-DAI
taker_market_trading_pair: ETH-USDT
taker_to_maker_base_conversion_rate: 1
taker_to_maker_quote_conversion_rate: 1
```

By default, taker to maker base conversion rate and taker to maker quote conversion rate value are both `1`.

Our maker base asset is WETH and taker is ETH. 1 WETH is worth 0.99 ETH (1 / 0.99) so we will set the `taker_to_maker_base_conversion_rate` value to 1.01.

While our maker quote asset is DAI, the taker is USDT, and 1 DAI is worth 1.01 USDT (1 / 1.01). Similar to the calculation we did for the base asset. In this case, we will set the `taker_to_maker_quote_conversion_rate` to 0.99.

To configure a parameter value without going through the prompts, input command as `config [ key ] [ value ]`. These can be reconfigured without stopping the bot. However, it will only take effect after restarting the strategy.

```
config taker_to_maker_base_conversion_rate 1.01
config taker_to_maker_quote_conversion_rate 0.99
```
