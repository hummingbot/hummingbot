# Huobi Global

Huobi is a global, centralized cryptocurrency exchange started in Seychelles and has since expanded its offices to Hong Kong, Korea, Japan, and the United States. As of March 2018, Huobi processed around US \$1 billion in trades daily.

## Using the connector

Because [Huobi](https://www.hbg.com/) is a centralized exchange, you will need to generate and provide your API key to trade using Hummingbot.

```
Enter your Huobi API key >>>
Enter your Huobi secret key >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip
    For copying and pasting into Hummingbot, see [this page](https://hummingbot.zendesk.com/hc/en-us/articles/900004871203-Copy-and-paste-your-API-keys) for more instructions in our Support section.

### Creating Huobi API keys

1. Log in to https://www.hbg.com/ or sign up for an account on [this page](https://www.hbg.com/en-us/register/?backUrl=%2Fen-us%2F) and go to **API Management** under **Account** section.

![huobi1](/assets/img/huobi-account.png)

2. Add notes (required) and make sure the checkbox for **Trade** is selected to trade on Hummingbot.

![huobi2](/assets/img/huobi-create-api-key.png)

!!! warning
    We recommend using only #trade# enabled API keys; enabling #withdraw, transfer or the equivalent is unnecessary# for current Hummingbot strategies.

!!! tip
    You will receive a notification and email when your API keys are about to expire.

3. **Click to send** and enter the verification code sent to the registered email address.

![huobi3](/assets/img/huobi-verification-code.png)

- Your Access Key and Secret Key will only be shown to you once. So make sure to save and keep this information somewhere safe. If you lose your Secret Key, you can delete the API and create a new one. However, it will be impossible to reuse the same API.
- Information related to your API keys such as create date, notes, permissions, bind IP address, days remaining before expiration, status is shown under **My API Key**. Click **Edit** button to change the permission setting or bind/unbind to an IP address anytime.

![huobi4](/assets/img/huobi-my-api-key.png)

## Miscellaneous info

### Minimum order sizes

You may refer to [this page](https://huobiglobal.zendesk.com/hc/en-us/articles/900000210246-Announcement-on-Adjusting-Minimum-Order-Amount-for-Some-Trading-Pairs) for the minimum order size per trading pair.

### Transaction fees

Huobi charges 0.2% on both maker and taker for most pairs. However, Huobi VIP users can also enjoy fees at a discounted rate.

No maker and taker fees for trading on stablecoins with HUSD (PAX/HUSD, USDC/HUSD, TUSD/HUSD, USDT/HUSD).

See [this page](https://www.hbg.com/en-us/about/fee/) for more information about their fees.

Users can override the default fees by editing [`conf_fee_overrides.yml`](/operation/override-fees/).
