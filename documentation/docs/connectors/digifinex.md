# Digifinex

DigiFinex is the world's top 10 crypto exchange by trading volume and liquidity, offering spot, leverage, perpetual swap trading, and fiat to crypto trading. We are widely loved for being stable, secure, and easy to use

## Using the connector

To use [Digifinex](https://www.digifinex.com/en-ww/login) connector, you will need to generate and provide your API key to trade using Hummingbot.

```
Enter your digifinex API key >>>
Enter your digifinex secret API key >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip
    For copying and pasting into Hummingbot, see [this page](https://hummingbot.zendesk.com/hc/en-us/articles/900004871203-Copy-and-paste-your-API-keys) for more instructions in our Hummingbot Help Center.

### Creating Digifinex API keys

1. Log in to your account at https://www.digifinex.com/en-ww/login, then click your profile > User Center (If you do not have an account, you will have to create one and verify your ID.)

!!! tip
    You must enable 2FA in your Digifinex account to create the API key. [How to enable 2FA](https://digifinex.zendesk.com/hc/en-us/signin?return_to=https%3A%2F%2Fdigifinex.zendesk.com%2Fhc%2Fen-us%2Farticles%2F360007869553--2FA-How-to-set-up-2FA)?

![](/assets/img/digifinex-account.png)

2. Then click on API settings.

![](/assets/img/digifinex-api-settings.png)

3. Click on Create API.

![](/assets/img/digifinex-create-api.png)

4. Give your API key a name. Check the corresponding box in which you will trade. It will need a verification code sent to your email and a code from your Authenticator.

![](/assets/img/digifinex-api.png)

Make sure you store your Secret Key somewhere secure and do not share it with anyone. Your Secret Key will only be displayed once at the time when you create the API.

!!! warning
    If you lose your Secret Key, you can delete the API and create a new one. However, it will be impossible to reuse the same API.

## Miscellaneous info

Users may experience WebSocket errors, and timeout may occur every 2 hours. In addition, there is a known server-side issue with regards to their rate limit, where users might be prematurely banned for exceeding rate limits. For more details on trading rules click [here](https://docs.digifinex.com/en-ww/v3/#digifinex-api-trading-rules).

### Minimum order sizes

Minimum order size varies per market. All minimum trade quantities can be found in the following public API:

```
https://openapi.digifinex.com/v3/markets
```

Refer to the API response below as an example:

```
{
    "data":
    [
      {
        "volume_precision":8,
        "price_precision":2,
        "market":"btc_usdt",
        "min_amount":2,
        "min_volume":5e-05
      },
      ...
    ]
},
```

You should focus on the data fields `min_volume`, which refers to the minimum order size based on base asset, and `min_amount`, which is based on quote asset.

### Transaction fees

The transaction fee for the Spot transaction is 0.2% per time. DFT holders can enjoy the discount. Become a VIP user and enjoy a lower transaction fee, with a minimum fee of 0.060%

- [Fees](https://digifinex.zendesk.com/hc/en-us/articles/360000328422--Contract-List-Fees)

Users can override the default fees by editing [`conf_fee_overrides.yml`](/operation/override-fees/)
