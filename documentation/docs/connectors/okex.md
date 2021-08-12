# OKEx

OKEx is a world-leading cryptocurrency exchange, providing advanced financial services to traders globally by using blockchain technology.

## Using the connector

Because OKEx is a centralized exchange, you will need to generate and provide your API key to trade using Hummingbot.

```
Enter your OKEx API key >>>
Enter your OKEx secret key >>>
Enter your OKEx passphrase key >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip
    For copying and pasting into Hummingbot, see [this page](https://hummingbot.zendesk.com/hc/en-us/articles/900004871203-Copy-and-paste-your-API-keys) for more instructions in our Support guide.

### Creating OKEx v5 API keys

1. Log into your account at https://www.okex.com, then select **Account>API** (If you do not have an account, you will have to create one and verify your ID).

2. Follow on-screen instructions to create your API keys. For your account's safety, please read the tips below before creating API keys.

!!! tip
    - For API key permissions, we recommend using only **trade** enabled API keys; enabling **withdraw**, **transfer**, or the equivalent is unnecessary for current Hummingbot strategies.
    - Make sure you store your Secret Key somewhere secure and do not share it with anyone. Your Secret Key will only be displayed once at the time when you create the API.
    - If you lose your Secret Key, you can delete the API and create a new one. However, it will be impossible to reuse the same API.

Here is the link for more info regarding the [OKEx upgrade to API v5](https://www.okex.com/academy/en/complete-guide-to-okex-api-v5-upgrade)

## Miscellaneous info

### Minimum order sizes

You have to check the individual trading pair for the information for the minimum order size per trading pair. See the following AAVE example: ![aave1](/assets/img/Okex-min-order.png)

### Transaction fees

By default, trading fees are 0.1% on OKEx for market makers and 0.15% for takers. Users who trade high volumes can receive more discounts on trading fees, see [OKex trading fees](https://www.okex.com/fees.html) for more details

Users can override the default fees by editing [`conf_fee_overrides.yml`](/operation/override-fees/).
