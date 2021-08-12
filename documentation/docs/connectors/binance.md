# Binance

Binance is a global cryptocurrency exchange that provides a platform for trading more than 100 cryptocurrencies. It is considered one of the top cryptocurrency trading platforms by volume. It also serves as a wallet for users who hold accounts on the exchange.

## Using the connector

Because Binance is a centralized exchange, you will need to generate and provide your API key to trade using Hummingbot.

```
Enter your Binance API key >>>
Enter your Binance secret key >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip
    For copying and pasting into Hummingbot, see [this page](https://hummingbot.zendesk.com/hc/en-us/articles/900004871203-Copy-and-paste-your-API-keys) for more instructions in our Hummingbot Help Center.

### Creating Binance API keys

1. Log into your account at https://www.binance.com, then select **Account** (If you do not have an account, you will have to create one and verify your ID).

!!! tip
    You must enable 2FA in your Binance account to create the API key. [How to enable 2FA](https://support.binance.com/hc/en-us/sections/360000011592-Two-Factor-Authentication)?

2. Click on **API Setting**.
   ![binance1](/assets/img/binance1.png)

3. Enter a key name and click on **Create New Key**.

![binance2](/assets/img/binance2.png)

4. Enter your 2FA code. Once you pass the authentication, Binance will send a confirmation mail to your registered email inbox. Please click “Confirm Create” to make the confirmation for the new API creation.

![binance3](/assets/img/binance3.png)

5. Now, you have created an API key. Please note that to trade on Binance using Hummingbot, **Enable Trading** must be selected

!!! warning
    For API key permissions, we recommend using only #trade# enabled API keys; enabling #withdraw#, #transfer#, or the equivalent is unnecessary for current Hummingbot strategies.

![binance4](/assets/img/binance4.png)

Make sure you store your Secret Key somewhere secure and do not share it with anyone. Your Secret Key will only be displayed once at the time when you create the API.

!!! warning
    If you lose your Secret Key, you can delete the API and create a new one. However, it will be impossible to reuse the same API.

## Miscellaneous info

### Minimum order sizes

See [this page](https://www.binance.com/en/trade-rule) for the minimum order size per trading pair. Typically, the minimum is around \$10 equivalent of whichever currency you are trading in.

### Transaction fees

By default, trading fees are 0.1% on Binance for both market makers and takers. However, users who trade high volumes and own substantial amounts of Binance Coin can receive discounts. More details can be found [here](https://www.binance.com/en/support/faq/115000429332).

Users can override the default fees by editing [`conf_fee_overrides.yml`](/operation/override-fees/).

### Sub-accounts

You can use an API key from a [Binance sub-account](https://medium.com/binanceexchange/binance-introduces-sub-account-support-d7bf2f95e28c) just like you do for a regular Binance account. Please ensure that you use the **sub-account API key** and not the master account API key.

If you are participating in [Liquidity Mining](https://docs.hummingbot.io/miner), please also use the **sub-account read-only API key** when you sign up.
