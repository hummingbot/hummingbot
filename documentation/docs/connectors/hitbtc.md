# HitBTC

HitBTC is a leading European bitcoin exchange that provides cryptocurrency trading services to institutional, merchants, and individual traders worldwide. The trading platform was founded in late 2013 and is under the operation of Ullus Corporation.

## Using the Connector

To use [HitBTC](https://hitbtc.com/) connector, you will need to generate and provide your API key to trade using Hummingbot.

```
Enter your hitbtc API key >>>
Enter your hitbtc secret key >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip
    For copying and pasting into Hummingbot, see [this page](https://hummingbot.zendesk.com/hc/en-us/articles/900004871203-Copy-and-paste-your-API-keys) for more instructions in our Hummingbot Help Center.

### Creating HitBTC API Keys

1. Log in to your account at https://hitbtc.com/signinapp, then click on settings, click on General Settings (If you do not have an account, you will have to create one and enable 2FA.).

!!! tip
    You must enable 2FA in your HitBTC account to create the API key. [How to enable 2FA](https://hitbtc.zendesk.com/hc/en-us/articles/360000719229-How-to-enable-2FA-with-a-code-generating-app)

![](/assets/img/hitbtc-settings.PNG)

![](/assets/img/hitbtc.PNG)

2. Click on API keys and then click "New API key"

![](/assets/img/hitbtc-api.PNG)

3. It will show that you have created your API keys. It will now display in your API keys.

![](/assets/img/hitbtc-api-key.PNG)

![](/assets/img/api-hitbtc.png)

4. Enable the permissions for `Order book, History, Trading balance,` and `Place/Cancel orders`. Again, 2FA code is needed for enabling permissions.

![](/assets/img/hitbtc-2fa.PNG)

![](/assets/img/hitbtc-api-permission.png)

5. Now that you have created an API key, connect it to Hummingbot using the `connect` command.

Make sure you store your Secret Key somewhere secure and do not share it with anyone. Your Secret Key will only be displayed once at the time when you create the API.

!!! warning
    If you lose your Secret Key, you can delete the API and create a new one. However, it will be impossible to reuse the same API.

## Miscellaneous info

### Minimum order size

Minimum order size varies per market. Also, it's called lot for hitBTC.

See [this page](https://blog.hitbtc.com/system-updates-lot-size-changes/) for more info.

!!! note
    USDT is labeled as USD.

### Transaction fees

The fees for Starter and General accounts are fixed at 0.1% Maker Fee and 0.25% Taker Fee.

- [Fees](https://hitbtc.com/fee-tier)

Users can override the default fees by editing [`conf_fee_overrides.yml`](/operation/override-fees/).
