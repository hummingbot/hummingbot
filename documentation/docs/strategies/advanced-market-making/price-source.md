# External Pricing Source Configuration

**Updated as of `v0.31.0`**

By default, Hummingbot uses the order book you're trading in to generate the **mid price** (between the top bid and the top ask) as a starting price to calculate maker order prices.

With this feature, users have the option to choose a different price reference for your orders such as **last trade price**, **last own trade price**, **best bid price** and **best ask price**. Users can also use a different order book such as an external **exchange** supported by Hummingbot or a **custom API**.


## How It Works

In a situation where the calculation of maker order prices from external sources would result in the order matching any existing orders on the order book, such order will be ignored unless `take_if_crossed` parameter is enabled.

### Price Source: Current Market

By default, `price_source` is set to `current_market` and `price_type` to `mid_price`.

```json
               exchange: binance
                 market: BTC-USDC
             bid_spread: 1
             ask_spread: 1
```

```json
           price_source: current_market
             price_type: mid_price
  price_source_exchange: None
    price_source_market: None
        take_if_crossed: None
price_source_custom_api: None
```

This means Hummingbot uses the mid price of the market's order book in the current exchange as reference e.g. if your bid/ask spread is set to 1, your orders will be created 1% away from the mid price.

Run `config price_type` command to change the price reference to `last_price`, `last_own_trade_price`, `best_bid`, and `best_ask`.


### Price Source: External Market

Users can also use an external market from another exchange supported by Hummingbot as the price reference when creating orders.

In the example below, we're trading on BTC-USDC pair in Binance while using the mid price of BTC-USDT market from Crypto.com exchange.

```json
               exchange: binance
                 market: BTC-USDC
             bid_spread: 1
             ask_spread: 1
```

```json
           price_source: external_market
             price_type: mid_price
  price_source_exchange: crypto_com
    price_source_market: BTC-USDT
        take_if_crossed: True
price_source_custom_api: None
```

Run `config price_type` command to change the price reference to `last_price`, `last_own_trade_price`, `best_bid`, and `best_ask`. The parameter `take_if_crossed` is optional as this only allows users to take existing orders from the order book if there is an existing match.

!!! note
    Currently, the external price source cannot be the same as the maker exchange (i.e. if the bot is trading on Binance, the `price_source_exchange` cannot be Binance).

### Price Source: Custom API

Custom API is mostly used by advanced users or developers for using a different price reference. Take note that `price_source` should be set to `custom_api` with the API URL indicated in `price_source_custom_api`.

```json
           price_source: custom_api
             price_type: mid_price
  price_source_exchange: None
    price_source_market: None
        take_if_crossed: None
price_source_custom_api: https://www.your-custom-api-url.com/
```

**Custom API Output Required Parameters**

The API GET request should return a decimal number corresponding to a market price for the asset pair you are trading on.

Sample API Output:

```json
207.8
```

## When to use an external price source

External price source is valuable when your bot is market making for a relatively illiquid trading pair, but a more liquid pair with the same underlying exposure is available on a different exchange.

Suppose we are market making for the `ETH-USDT` trading pair. The exchange we are trading on, denoted as **Exchange A**, has the top bid order at $198 and the top ask order at $202, so the mid price is $200.

Let's suppose there is **Exchange B** with an `ETH-USD` trading pair. That pair has a top bid order at $200 while the top ask order is $202, so the mid price is $201. These discrepancies often happens between different exchanges as market conditions change. Some exchanges may react more slowly or quickly to market changes due to differences in the trading pair, liquidity, geography.

If you believe that `ETH-USD` on Exchange B is more liquid and responds more quickly to market information than `ETH-USDT` on Exchange A, you may want to market make on Exchange A but use `ETH-USD` on Exchange B as the price source. This helps you position your orders based on where the market might go in the future. 


## Taking Crossed Orders

When using an external price source, an order may result in a crossed market. This means the order on the current exchange is placed with a price that matches an existing order in the book. Enabling `take_if_crossed` parameter allows the strategy to fill the matching maker order.

In certain cases, this behavior may be desirable even if the fee is higher because of the likely future price mitigation. This feature is only available when an external price source is used. When enabled, Hummingbot uses `LIMIT` order instead of `LIMIT_MAKER` order type.


## Relevant Parameters

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **price_source** | `Which price source to use? (current_market/external_market/custom_api)` | Determines which market to be used as price reference when creating orders.
| **price_type** | `Which price type to use? (mid_price/last_price/last_own_trade_price/best_bid/best_ask)` | Price type to be used as price reference when creating orders.
| **price_source_exchange** | `Enter external price source exchange name` | Name of exchange to be used for external pricing source. |
| **price_source_market** | `Enter the token pair on [price_source_exchange]` | The trading pair for the price source exchange. |
| **take_if_crossed** | `Do you want to take the best order if orders cross the orderbook? (Yes/No)` | Take order if they cross orderbook when external price source is enabled. |
| **price_source_custom_api** | `Enter pricing API URL` | An external API that returns price. |
