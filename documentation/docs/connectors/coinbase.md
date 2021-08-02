# Coinbase Pro

Based in San Francisco, CA, Coinbase Pro is a widely-used, global cryptocurrency exchange designed for professional traders. It has a reputation for being secure and trustworthy, is [regulated in all the jurisdictions in which it operates](https://www.coinbase.com/legal/insurance), and maintains some [insurance on assets and deposits](https://www.coinbase.com/legal/insurance).

## Using the connector

Because Coinbase Pro is a centralized exchange, you will need to generate and provide your API key to trade using Hummingbot.

```
Enter your Coinbase API key >>>
Enter your Coinbase secret key >>>
Enter your Coinbase passphrase >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip
    For copying and pasting into Hummingbot, see [this page](https://hummingbot.zendesk.com/hc/en-us/articles/900004871203-Copy-and-paste-your-API-keys) for more instructions in our Support guide.

### Creating Coinbase Pro API keys

1. Log into your Coinbase Pro account, click your avatar and then select **API** (If you do not have an account, you will have to create one and verify your ID).

![coinbase1](/assets/img/coinbase1.png)

!!! tip
    You must enable 2FA in your Coinbase account to create the API key. [How to enable 2FA](https://support.coinbase.com/customer/en/portal/articles/1658338-how-do-i-set-up-2-factor-authentication-)?

2. Click on **+ NEW API KEY**.

![coinbase2](/assets/img/coinbase2.png)

Make sure you give permissions to **View** and **Trade**, and enter your 2FA code.

!!! warning
    We recommend using only #trade# enabled API keys; enabling #withdraw, transfer, or the equivalent is unnecessary# for current Hummingbot strategies.

![coinbase3](/assets/img/coinbase3.png)

Once you pass the authentication, you’ve created a new API Key!

Your API Secret will be displayed on the screen. Make sure you store your API Secret somewhere secure and do not share it with anyone.

![coinbase4](/assets/img/coinbase4.png)

When you close the API Secret screen, your API key will be shown in **My API Keys**. The code highlighted in red is your API key.

![coinbase5](/assets/img/coinbase5.png)

The API Key, Secret, and Passphrase are required for using Hummingbot.

!!! warning
    If you lose your Secret Key, you can delete the API and create a new one. However, it will be impossible to reuse the same API.

## Miscellaneous info

### Trading pair limitations

Coinbase Pro has trading pair limitations in certain regions. For example, some countries have access to crypto/fiat trading pairs, while other countries can only access crypto/crypto trading pairs.

Running Hummingbot with this connector on a pair that your country has no access to will result in this error:

```
OSError: Error fetching data from https://api.pro.coinbase.com/orders.
HTTP status is 400. {'message': 'Trading pair not available'}
```

For more information, read through their article below.

- [Locations and trading pairs](https://help.coinbase.com/en/pro/trading-and-funding/cryptocurrency-trading-pairs/locations-and-trading-pairs)

### Minimum order sizes

All Market Orders, Limit Orders and Stop Orders placed on Coinbase Markets are subject to the minimum order size requirements listed in their [Market Information](https://pro.coinbase.com/markets) page.

![coinbase6](/assets/img/coinbase6.png)

### Transaction fees

Coinbase Pro charges 0.50% fees for both maker and taker orders. However, users who trade in high volumes can trade at discounted rates.

Read through their article below related to trading fees and discounts.

- [What are the fees on Coinbase Pro?](https://help.coinbase.com/en/pro/trading-and-funding/trading-rules-and-fees/fees.html)

Users can override the default fees by editing [`conf_fee_overrides.yml`](/operation/override-fees/).
