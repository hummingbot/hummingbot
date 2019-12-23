# Liquid Connector

## About Liquid

Liquid is a centralized exchange based in Tokyo, Japan launched by Quione in 2017. It also has offices in Singapore but is regulated and licensed by the Financial Services Agency of Japan. Over the past 12 months (as at May 2019) it has more than USD 50 billion in transactions on their exchanges.


## Using the Connector

The connector is for [Liquid](https://www.liquid.com/) based in Singapore (i.e. not for the local Japanese Liquid exchange). Because it is a centralized exchange, you will need to generate and provide your API key in order to trade using Hummingbot.

```
Enter your Liquid API key >>>
Enter your Liquid secret key >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip "Copying and pasting into Hummingbot"
    See [this page](https://docs.hummingbot.io/support/how-to/#how-do-i-copy-and-paste-in-docker-toolbox-windows) for more instructions in our Get Help section.


### Creating Liquid API keys

This article below in their website under API information shows step-by-step instructions on how to create API keys in Liquid exchange.

* [How to create API tokens](https://help.liquid.com/en/articles/2285018-how-to-create-api-tokens)

!!! warning "API key permissions"
    We recommend using only **"trade"** enabled API keys; enabling **"withdraw", "transfer", or the equivalent** is unnecessary for current Hummingbot strategies.


## Miscellaneous Info

### Minimum Order Sizes

There is no minimum order quantity for trading fiat currency. See [this page](https://help.liquid.com/en/articles/3339119-minimum-order-quantity) for minimum order sizes on crypto trading pairs.

## Transaction Fees

Generally, Liquid charges 0.10% on both maker and taker while a user can get 50% discount on trading fees if paid in QASH. QASH is an ERC20 token designed to be used services on the Quione and Liquid platform. Effecive April 1 2019, high-volume traders can also get rebates on trading fees.

Read through their articles below related to trading fees, and rebates.

* [Trading Fees](https://help.liquid.com/en/articles/2273126-trading-fees)
* [Trading fee rebate for high-volume traders](https://help.liquid.com/en/articles/2825019-trading-fee-rebate-for-high-volume-traders)