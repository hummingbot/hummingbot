# External Pricing Source Configuration

By default, Hummingbot uses the market orderbook mid price (between the top bid and the top ask) as a starting price to calculate maker order prices. 
With external pricing sources, you can now use external sources for the starting mid price such as an external **exchange**, **data feed**, or a **custom API**.

In a situation where the calculaton of maker order prices from external sources would result in the order matching any existing orders on the order book, such order will be ignored. For example, if ETH-USDC market is currently displaying 109 bid and 111 ask. A specified external exchange is showing 99 bid and 101 ask on its book (mid price = 100). 2 maker orders will be proposed, a bid maker order at 98 (for 2% bid spread) and an ask maker order at 102 (for 2% ask spread). The 102 ask order will be ignored (as it would match the 109 bid order), only the bid order will be submitted to the exchange. 


## Relevant Parameters

| Parameter | Prompt | Definition | Default Value |
|-----------|--------|------------|---------------|
| **external_pricing_source** | `Would you like to use an external pricing source for mid-market price? (Yes/No) >>>` | Whether to use external pricing source for the mid price. | `false` |
| **external_price_source_type** | `Which type of external price source to use? (exchange/feed/custom_api) >>>` | The type of external pricing source (exchange/feed/custom_api) | none |
| **external_price_source_exchange** | `Enter exchange name >>> ` | An external exchange name (for external exchange pricing source) | none |
| **external_price_source_exchange_trading_pair** | |  A trading pair for the external exchange (for external exchange pricing source). | none |
| **external_price_source_feed_base_asset** | `Reference base asset from data feed? (e.g. ETH) >>>` | A base asset, e.g. ETH (for external feed pricing source). | none |
| **external_price_source_feed_quote_asset** | `Reference quote asset from data feed? (e.g. USD) >>>` | A quote asset, e.g. USD (for external feed pricing source). | none |
| **external_price_source_custom_api** | `Enter pricing API URL >>>` | An external api that returns price (for external custom_api pricing source). | none |