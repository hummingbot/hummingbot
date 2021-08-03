# Binance Futures

<meta charset="utf-8" />

Binance Futures is the fastest-growing crypto-derivative exchange by trading volume and currently offers the highest leverage of 125x margin among major crypto exchanges, making it one of the most competitive products in the market. This was made possible by our robust risk management system, which includes a sophisticated risk engine, smart liquidation model, and insurance funds that provide traders with extra protection for highly leveraged trading.

## Using the connector

Like the Binance connector, you will need to generate and provide your API key to trade using Hummingbot.

```
Enter your Binance Perpetual API key >>>
Enter your Binance Perpetual API secret >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip
    For copying and pasting into Hummingbot, see [this page](https://hummingbot.zendesk.com/hc/en-us/articles/900004871203-Copy-and-paste-your-API-keys) for more instructions in our Hummingbot Help Center.

### Creating Binance Futures API keys

1. Log into your account at https://www.binance.com, then select **Account**> **API Management** (If you do not have an account, you will have to create one and verify your ID).
2. Follow on-screen instructions to create your API keys.
3. After creating the API key, click **Edit restrictions** and tick **Enable Futures** to enable future tradings on your API key.

![](/assets/img/api-restriction.jpg)

> **Important:**

- If you don't see **Enable Futures** under your API key permissions, you need to open a Futures account by simply going to **Derivatives** > **USDT features** > **Open account**
- For API key permissions, we recommend using only **"trade"** enabled API keys for **Enable Futures** checkbox; enabling **"withdraw", "transfer", or the equivalent is unnecessary** for current Hummingbot strategies.
- Make sure you store your Secret Key somewhere secure and do not share it with anyone. Your Secret Key will only be displayed once at the time when you create the API.
- If you lose your Secret Key, you can delete the API and create a new one. However, it will be impossible to reuse the same API.

### Creating Binance Futures Testnet API Keys

If you’d like to test without risking real funds, you can try out the Binance Futures testnet.

1. Login or register for a new account at https://testnet.binancefuture.com/
2. Under **Position and Open orders**, select **API key** tab and your Binance Futures testnet API key will be automatically generated.

![](/assets/img/testnet-api.jpg)

## Contract specifications of Binance Perpetuals

- Trading Rules: Please see [Binance future trading rules](https://www.binance.com/en/futures/trading-rules)
- Leverage and Margin: Please see [Leverage and Margin](https://www.binance.com/en/support/faq/360033162192)
