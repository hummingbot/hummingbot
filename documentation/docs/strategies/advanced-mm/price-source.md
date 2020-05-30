# External Pricing Source Configuration

**Updated as of `v0.28.0`**

By default, Hummingbot uses the market orderbook mid price (between the top bid and the top ask) as a starting price to calculate maker order prices. 
With external pricing sources, you can now use external sources for the starting mid price such as an external **exchange** or a **custom API**.

##How It Works

In a situation where the calculation of maker order prices from external sources would result in the order matching any existing orders on the order book, such order will be ignored.

Type `config price_source_enabled` to set the values for `price_source_enabled`, `price_source_type`, `price_source_exchange` and `price_source_market`, or `price_source_custom` (if source type is exchange). Type `config` + `price_source_type`, `price_source_exchange`, `price_source_market`, or `price_source_custom` to set values for these parameters.

Note that the external price source cannot be the same as the maker exchange (i.e. if the bot is trading on Binance, the `price_source_exchange` cannot be Binance). 

###Example - When Price Sourcing is Important
Suppose we are market making on the `ETH-USDT` trading pair. The exchange we are trading on, denote as **Exchange A**, is currently displaying a 109 bid and 111 ask price. Now let us consider an **Exchange B** that is showing 99 bid and 101 ask prices on its book. This discrepancy often happens between liquid (B) and illiquid (A) exchanges. When this kind of discrepancy occurs, traders on both exchanges will arbitrage out the discrepancy naturally. Thus, one would want to position their trades with respect to the liquid exchange (**Exchange B**) because the price is likely going to move toward the liquid exchange. Now, when we trade using our market-making bot, we also want to position ourselves towards the more liquid exchange. So, we use **Exchange B** as an *External Price Source*. The trading strategy thus proposes two maker orders, a bid maker order at 98 (for 2% bid spread above the mid-market price of Exchange B) and an ask maker order at 102 (for 2% ask spread on Exchange B). The 102 ask order will be ignored (as it would match the 109 bid order), only the bid order will be submitted to the exchange. Ultimately, this tool is extremely valuable when your bot is trading on illiquid exchanges.


## Sample Configurations
```json
- market: XRP-USD
- bid_spread: 1
- ask_spread: 1
- order_amount: 56
```
###No External Pricing Source Configuration
![No External Pricing Source Configuration](/assets/img/price_source_None_config.PNG)

###Exchange External Price Source Configuration
![Exchange External Price Source Configuration](/assets/img/price_source_exchange_config.PNG)

###Custom API Pricing Source Configuration
![Custom API Pricing Source Configuration](/assets/img/price_source_custom_api_config.PNG)

**Custom API Output Required Parameters**

The API GET request should return a decimal number corresponding to a market price for the asset pair you are trading on.


*Sample API Output:*
```json
207.8
```


## Relevant Parameters

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **price_source_enabled** | `Would you like to use an external pricing source for mid-market price? (Yes/No)` | When enabled, allows users to use an external pricing source for the mid price. |
| **price_source_type** | `Which type of external price source to use? (exchange/custom_api)` | The type of external pricing source. |
| **price_source_exchange** | `Enter external price source exchange name` | Name of exchange to be used for external pricing source. |
| **price_source_market** | `Enter the token pair on [price_source_exchange]` | The trading pair for the price source exchange. |
| **price_source_custom** | `Enter pricing API URL` | An external API that returns price. |