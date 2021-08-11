# Liquid

Liquid is a centralized exchange based in Tokyo, Japan launched by Quione in 2017. It also has offices in Singapore but is regulated and licensed by the Financial Services Agency of Japan. Over the past 12 months (as of May 2019), it has more than USD 50 billion in transactions on its exchanges.

## Using the connector

The connector is for [Liquid](https://www.liquid.com/) based in Singapore (i.e., not for the local Japanese Liquid exchange). Because it is a centralized exchange, you will need to generate and provide your API key to trade using Hummingbot.

```
Enter your Liquid API key >>>
Enter your Liquid secret key >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip
    For copying and pasting into Hummingbot, see [this page](https://hummingbot.zendesk.com/hc/en-us/articles/900004871203-Copy-and-paste-your-API-keys) for more instructions in our Support guide.

### Creating Liquid API keys

The article below in their website under API information shows step-by-step instructions on creating API keys in Liquid exchange.

- [How to create API tokens](https://help.liquid.com/en/articles/2285018-how-to-create-api-tokens)

!!! warning
    For API key permissions, we recommend using only #orders# enabled (read and write) API keys; enabling #withdraw, transfer or the equivalent# is unnecessary for current Hummingbot strategies.

## Miscellaneous info

### Exchange status

Users can go to https://status.liquid.com/ to check the status of the exchange and review past or ongoing incidents.

Developers can query the current status using the API. See documentation in https://status.liquid.com/api/.

### Minimum order sizes

There is no minimum order quantity for trading fiat currency. Instead, see [this page](https://help.liquid.com/en/articles/4141955-liquid-buy-faq) for minimum order sizes on crypto trading pairs.

If the token or trading pair isn't listed in the article, you can also get this information through their public API.

```
https://api.liquid.com/currencies
```

The minimum order size is the value next to `minimum_order_quantity`. For example, you're trading ETH-BTC, and ETH, your **base currency**, is not listed in the above article. Liquid's public API shows the minimum order size of ETH currency is `0.01`.

```
"currency_type": "crypto",
"currency": "ETH",
"symbol": "Ξ",
"assets_precision": 18,
"quoting_precision": 8,
"minimum_withdrawal": 0.02,
"withdrawal_fee": 0.0,
"minimum_fee": null,
"minimum_order_quantity": 0.01,
"display_precision": 5,
"depositable": true,
"withdrawable": true,
"discount_fee": 0.5,
"lendable": true,
"position_fundable": true,
"has_memo": false
```

### Transaction fees

In this [blog post](https://blog.liquid.com/liquid-progressive-fee-update), Liquid announced their [new fee structure](https://www.liquid.com/fees/) that offers 0 trading fees on maker orders if a user's 30-day trading volume is less than \$10,000 and 0.30% on the taker. In addition, all users can get a 50% discount on trading fees if paid in QASH.

QASH is an ERC20 token designed to be used services on the Quione and Liquid platform. Effective April 1, 2019, high-volume traders can also get rebates on trading fees.

Read through their articles below related to trading fees and rebates.

- [Trading Fees](https://www.liquid.com/fees/)
- [Trading fee rebate for high-volume traders](https://help.liquid.com/en/articles/2825019-trading-fee-rebate-for-high-volume-traders)

Users can override the default fees. See [Fee Overrides](/operation/override-fees).
