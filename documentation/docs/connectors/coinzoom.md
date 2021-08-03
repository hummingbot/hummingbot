# CoinZoom

CoinZoom is an institutional-grade digital currency trading platform that uses the team’s vast experience in providing superb trade quality and customer-focused tools and technology to help our customers to become successful digital currency traders. CoinZoom will offer Buying, Selling, and Trading of Bitcoin, Ripple, Ethereum, and other top digital currency pairs. In addition, our decades of experience in financial technology security are equally important in safeguarding customer funds and customers' digital currency positions.

It was established back on March 18, 2018. a Utah-based cryptocurrency exchange announced the official launch of its exchange and CoinZoom Visa card.

## Using the connector

To use [CoinZoom](https://www.coinzoom.com) connector, you will need to generate and provide your API key to trade using Hummingbot.

```
Enter your CoinZoom API key >>>
Enter your CoinZoom secret API key >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip
    For copying and pasting into Hummingbot, see [this page](https://hummingbot.zendesk.com/hc/en-us/articles/900004871203-Copy-and-paste-your-API-keys) for more instructions in our Hummingbot Help Center.

### Creating CoinZoom API keys

1. Log in to your account at https://trade.coinzoom.com/login, then go to > API trading (If you do not have an account, you will have to create one and verify your ID.)

![](/assets/img/coinzoom-api-trading.png)

!!! tip
    You must enable 2FA in your Coinzoom account to create the API key. [How to enable 2FA](https://support.coinzoom.com/en/support/solutions/articles/43000574216-two-factor-authentication-faqs)?

2. Then click “Generate key”

![](/assets/img/coinzoom-generate-api.png)

3. Now that you have created an API key, connect it to Hummingbot using the `connect` command.

![](/assets/img/coinzoom-api.png)

Make sure you store your Secret Key somewhere secure and do not share it with anyone. Your Secret Key will only be displayed once at the time when you create the API.

!!! warning
    If you lose your Secret Key, you can delete the API and create a new one. However, it will be impossible to reuse the same API.

## Miscellaneous info

### Transaction fees

By default, trading fees for this exchange charge a fee of 0.20% for makers and 0.26% for takers per trade.

- [Fees](https://www.coinzoom.com/fees/)

Users can override the default fees by editing [`conf_fee_overrides.yml`](/operation/override-fees/).
