# Binance US

Launched in September 2019, Binance.US is a digital asset marketplace powered by matching engine and wallet technologies licensed from the world's largest cryptocurrency exchange, Binance. Operated by BAM Trading Services based in San Francisco, California, Binance.US provides a fast, secure and reliable platform to buy and sell cryptocurrencies in the United States.

## Using the connector

Because Binance US is a centralized exchange, you will need to generate and provide your API key to trade using Hummingbot.

```
Enter your Binance US API key >>>
Enter your Binance US secret key >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip
    For copying and pasting into Hummingbot, see [this page](https://hummingbot.zendesk.com/hc/en-us/articles/900004871203-Copy-and-paste-your-API-keys) for more instructions in our Hummingbot Help Center.

### Creating Binance.us API keys

1. Log into your account at https://www.binance.us, then select **Account>API Management** (If you do not have an account, you will have to create one and verify your ID).
2. Follow on-screen instructions to create your API keys
   > **Important:**
   - For API key permissions, we recommend using only **"trade"** enabled API keys; enabling **"withdraw", "transfer", or the equivalent is unnecessary** for current Hummingbot strategies.
   - Make sure you store your Secret Key somewhere secure and do not share it with anyone. Your Secret Key will only be displayed once at the time when you create the API.
   - If you lose your Secret Key, you can delete the API and create a new one. However, it will be impossible to reuse the same API.

## Miscellaneous info

### Minimum order sizes

See [this page](https://www.binance.us/en/trade-limits) for the minimum order size per trading pair. Typically, the minimum is around \$10 equivalent of whichever currency you are trading in.

### Transaction fees

By default, [trading fees](https://www.binance.us/en/fee/schedule) are 0.1% on Binance for both market makers and takers. However, users who trade high volumes and own substantial amounts of Binance Coin can receive discounts. More details can be found [here](https://www.binance.com/en/support/articles/115000429332-Fee-Structure-on-Binance).

Users can override the default fees by editing [`conf_fee_overrides.yml`](/operation/override-fees/).
