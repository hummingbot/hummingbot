# Bitfinex

## About Bitfinex

Bitfinex is a cryptocurrency exchange owned and operated by iFinex Inc., headquartered in Hong Kong and registered in the British Virgin Islands.

Bitfinex was founded in December 2012 as a peer-to-peer Bitcoin exchange, offering digital asset trading services to users worldwide. Bitfinex initially started as a P2P margin lending platform for Bitcoin and later added support for more cryptocurrencies.

## Using the connector

To use Bitfinex connector, you will need to generate and provide your API key to trade using Hummingbot.

```
Enter your Bitfinex key >>>
Enter your Bitfinex secret key >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only.
At no point will private or API keys be shared with someone or be used in any way other
than to authorize transactions required for the operation of Hummingbot.

!!! tip
    For copying and pasting into Hummingbot, see [this page](https://hummingbot.zendesk.com/hc/en-us/articles/900004871203-Copy-and-paste-your-API-keys) for more instructions in our Support guide.

### Creating Bitfinex API keys

1. Log into your Bitfinex account, click your avatar and then select **account**, after choose **API** (If you do not have an account, you will have to create one).

![bitfinex1](/assets/img/bitfinex1.png)

!!! tip
    For more secure, enable 2FA in your account. [How to enable 2FA](https://support.bitfinex.com/hc/en-us/articles/115003340249-Google-Authenticator-2FA-Setup)?

2. Click on **Create NEW KEY**.

![bitfinex2](/assets/img/bitfinex2.png)

Make sure you give permissions to **Read** and **Write** and enter your 2FA code.

Confirm your API-key request bypass the link in the email letter. You will receive a notification: _Almost Done! Please check your email to complete the creation of this new API key._

!!! warning
    For API key permissions, we recommend using #Orders# enabled API keys; enabling #withdraw#, or the equivalent is unnecessary for current Hummingbot strategies.

Once you pass the link in an email letter, you've created a new API Key!

Your API Secret will be displayed on the screen. Make sure you store your API Secret somewhere secure and do not share it with anyone.

![bitfinex3](/assets/img/bitfinex3.png)

The API key and API secret key are required for using Hummingbot.

!!! warning
    If you lose your Secret Key, you can delete the API and create a new one. However, it will be impossible to reuse the same API.

## Miscellaneous info

### Minimum order sizes

Pairs on Bitfinex generally require a minimum order size equivalent to between \$2.5 and more. You can access the minimum order size for a specific token pair using Bitfinex's API at the following URL:

```
https://api-pub.bitfinex.com/v2/conf/pub:info:pair
```

You can use an application like [Postman](https://www.postman.com/) that gets REST API data or copy and paste the URL in your web browser.

### Transaction fees

Bitfinex charges 0.1% in maker fees and 0.2% in taker fees for most users. However, users who trade in high volumes can trade at discounted rates. See the article below for more details.

- [Fees Schedule](https://www.bitfinex.com/fees)

Users who are on discounted fees can override the default fees used in the Hummingbot client by following our guide for [Fee Overrides](/operation/override-fees).
