# Huobi Global Connector

## About Huobi Global

Huobi is a global, centralized cryptocurrency exchange that was started in Singapore, and has since expanded its offices to Hong Kong, Korea, Japan, and the United States. As of March 2018, Huobi processed around US $1 billion in trades daily.


## Using the Connector

Because [Huobi](https://www.hbg.com/) is a centralized exchange, you will need to generate and provide your API key in order to trade using Hummingbot.

```
Enter your Huobi API key >>>
Enter your Huobi secret key >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip "Copying and pasting into Hummingbot"
    See [this page](https://docs.hummingbot.io/support/how-to/#how-do-i-copy-and-paste-in-docker-toolbox-windows) for more instructions in our Get Help section.


### Creating Huobi API Keys

1 - Log in to https://www.hbg.com/ or sign up for an account in [this page](https://www.hbg.com/en-us/register/?backUrl=%2Fen-us%2F) and go to **API Management** under **Account** section.

![huobi1](/assets/img/huobi-account.png)

2 - Add notes (required) and make sure the checkbox for **Trade** is selected to trade on Hummingbot.

!!! warning "API key permissions"
    We recommend using only **"trade"** enabled API keys; enabling **"withdraw", "transfer", or the equivalent** is unnecessary for current Hummingbot strategies.

![huobi2](/assets/img/huobi-create-api-key.png)

!!! tip
    You will receive a notification and email when your API keys are about to expire.

3 - **Click to send** and enter the verification code sent to the registered email address.

![huobi3](/assets/img/huobi-verification-code.png)

4 - Your Access Key and Secret Key will only be shown to you once. Make sure to save and keep this information somewhere safe. If you lose your Secret Key, you can delete the API and create a new one. However, it will be impossible to reuse the same API.

5 - Information related to your API keys such as create date, notes, permissions, bind IP address, days remaining before expiration, status are shown under **My API Key**. Click **Edit** button to change the permission setting or bind/unbind to an IP address anytime.

![huobi4](/assets/img/huobi-my-api-key.png)



## Miscellaneous Info

### Minimum Order Sizes

You may refer to [this page](https://support.huobi.so/hc/en-us/articles/360000400491-Trade-Limits) for the minimum order size per trading pair.

## Transaction Fees

Huobi charges 0.2% on both maker and taker for most pairs. However, Huobi VIP users can also enjoy fees at discounted rate.

No maker and taker fees for trading on stablecoins with HUSD (PAX/HUSD, USDC/HUSD, TUSD/HUSD, USDT/HUSD).

See [this page](https://www.hbg.com/en-us/about/fee/) for more information about their fees.
