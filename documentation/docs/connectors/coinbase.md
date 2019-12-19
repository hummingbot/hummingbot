# Coinbase Pro Connector

## About Coinbase Pro

Coinbase Pro is a highly popular, global cryptocurrency exchange designed for professional traders based out of San Francisco, California. It has a reputation for being secure and trustworthy, and accounts on the exchange backed by FDIC insurance.

## Using the Connector

Because Coinbase Pro is a centralized exchange, you will need to generate and provide your API key in order to trade using Hummingbot.

```
Enter your Coinbase API key >>>
Enter your Coinbase secret key >>>
Enter your Coinbase passphrase >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip "Copying and pasting into Hummingbot"
    See [this page](https://docs.hummingbot.io/support/how-to/#how-do-i-copy-and-paste-in-docker-toolbox-windows) for more instructions in our Get Help section.

### Creating Coinbase Pro API Keys

1 - Log into your Coinbase Pro account, click your avatar and then select **API** (If you do not have an account, you will have to create one and verify your ID).

![coinbase1](/assets/img/coinbase1.png)

!!! tip "Important tip"
    You must enable 2FA in your Coinbase account to create the API key. [How to enable 2FA?](https://support.coinbase.com/customer/en/portal/articles/1658338-how-do-i-set-up-2-factor-authentication-)

2 - Click on **+ NEW API KEY**.

![coinbase2](/assets/img/coinbase2.png)

Make sure you give permissions to **View** and **Trade**, and enter your 2FA code.

!!! warning "API key permissions"
    We recommend using only **"trade"** enabled API keys; enabling **"withdraw", "transfer", or the equivalent** is unnecessary for current Hummingbot strategies.

![coinbase3](/assets/img/coinbase3.png)

Once you pass the authentication, you’ve created a new API Key!

Your API Secret will be displayed on the screen. Make sure you store your API Secret somewhere secure, and do not share it with anyone.

![coinbase4](/assets/img/coinbase4.png)

When you close the API Secret screen, your API key will be shown in **My API Keys**. The code highlighted in red is your API key.

![coinbase5](/assets/img/coinbase5.png)

The API Key, Secret, and Passphrase are required for using Hummingbot.

!!! warning
    If you lose your Secret Key, you can delete the API and create a new one. However, it will be impossible to reuse the same API.

## Miscellaneous Info

### Minimum Order Sizes

Pairs on Coinbase Pro generally require a minimum order size equivalent to between $5 and $10. The specific details for different base pairs can be found [here](https://www.coinbase.com/legal/trading_rules).

### Transaction Fees

Coinbase Pro charges 0.15% in maker fees and 0.25% in taker fees for most users. However, users who trade in high volumes can trade at discounted rates. See their [official fee structure](https://pro.coinbase.com/fees) for more details.
