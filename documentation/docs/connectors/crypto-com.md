# Crypto.com

Crypto.com was founded in 2016 on a simple belief: it’s a basic human right for everyone to control their money, data, and identity. Crypto.com serves over 3 million customers today, providing them with a powerful alternative to traditional financial services through the Crypto.com App, the Crypto.com Card, and the Crypto.com Exchange.

## Using the connector

[Crypto.com](https://crypto.com/exchange) is a centralized exchange and you will need to connect your API keys to Hummingbot for trading.

```
Enter your Crypto.com API key >>>
Enter your Crypto.com secret key >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

### Creating Crypto.com API keys

This help article below shows step-by-step instructions on how to create API keys in the exchange.

- [How do I create an API key?](https://exchange-docs.crypto.com/spot/index.html#introduction)

!!! warning
        We recommend using only #trade# enabled API keys; enabling #withdraw, transfer, or the equivalent is unnecessary# for current Hummingbot strategies.

## Miscellaneous info

### Minimum order sizes

The minimum order size for each trading pair is denominated in **base currency**. You can access the minimum order size for a specific token pair using [Crypto.com's API](https://exchange-docs.crypto.com/#public-get-instruments) at the following URL:

```
https://api.crypto.com/v2/public/get-instruments
```

You can use an application like [Postman](https://www.postman.com/) that gets REST API data or copy and paste the URL in your web browser.

The `quantity_decimals` value is the market's minimum trade size.

```
{
    "instrument_name": "BTC_USDT",
    "quote_currency": "USDT",
    "base_currency": "BTC",
    "price_decimals": 2,
    "quantity_decimals": 6
},
{
    "instrument_name": "CRO_USDT",
    "quote_currency": "USDT",
    "base_currency": "CRO",
    "price_decimals": 4,
    "quantity_decimals": 3
},
{
    "instrument_name": "XLM_BTC",
    "quote_currency": "BTC",
    "base_currency": "XLM",
    "price_decimals": 8,
    "quantity_decimals": 0
},
```

In the example above, the minimum order size for BTC-USDT pair is `0.000001 BTC`, CRO-USDT minimum order is `0.001 CRO`, and XLM-BTC minimum is `1 XLM`.

### Transaction fees

Crypto.com charges 0.10% on maker fees and 0.16% on taker fees for users on the VIP1 tier, while others who trade high volumes or use CRO to pay for trading fees can get discounts.

Read through their help articles below for more information.

- [Fees & Limits](https://crypto.com/exchange/document/fees-limits)
- [Fees & Trading Volume](https://help.crypto.com/en/articles/3511276-fees-trading-volume)

Unlike other connectors, overriding the fee calculated by Hummingbot on trades by editing `conf_fee_overrides.yml` file will not work.

Crypto.com connector uses the trade info, including the actual amount of fees paid. You can confirm this in the CSV file inside the `data` folder.

![crypto_com](/assets/img/crypto_com_csv.png)
