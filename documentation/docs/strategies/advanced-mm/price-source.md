# External Pricing Source Configuration
By default, Hummingbot uses the market order book mid price (between the top bid and the top ask) as a starting price to calculate maker order prices. 
With external pricing sources, you can now use below external sources for the starting mid price. 

| Prompt | Description |
|-----|-----|
| `Would you like to use an external pricing source for mid-market price? (Yes/No) >>>` | This sets `external_pricing_source` ([definition](#configuration-parameters)). |
| `Which type of external price source to use? (exchange/feed/custom_api) >>>` | This sets `external_price_source_type` ([definition](#configuration-parameters)). |

- Exchange

An external exchange that is supported by Hummingbot.

| Prompt | Description |
|-----|-----|
| `Enter exchange name >>> ` | This sets `external_price_source_exchange` ([definition](#configuration-parameters)). |

- Feed

Coin Market Cap or Coin Gecko data feed will be used.

| Prompt | Description |
|-----|-----|
| `Reference base asset from data feed? (e.g. ETH) >>> ` | This sets `external_price_source_feed_base_asset` ([definition](#configuration-parameters)). |
| `Reference quote asset from data feed? (e.g. USD) >>> ` | This sets `external_price_source_feed_quote_asset` ([definition](#configuration-parameters)). |

- Custom_API

An external API which provides price update continously.

| Prompt | Description |
|-----|-----|
| `Enter pricing API URL >>> ` | This sets `external_price_source_custom_api` ([definition](#configuration-parameters)). |

In a situation where the calculaton of maker order prices from external sources would result in the order matching any existing orders on the order book, such order will be ignored. For example, if ETH-USDC market is currently displaying 109 bid and 111 ask. A specified external exchange is showing 99 bid and 101 ask on its book (mid price = 100). 2 maker orders will be proposed, a bid maker order at 98 (for 2% bid spread) and an ask maker order at 102 (for 2% ask spread). The 102 ask order will be ignored (as it would match the 109 bid order), only the bid order will be submitted to the exchange. 
