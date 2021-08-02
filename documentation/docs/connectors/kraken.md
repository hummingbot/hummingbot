# Kraken

Kraken is a centralized exchange based in San Francisco, CA, founded in 2011. Users can trade several cryptocurrencies and various fiat currencies such as USD, CAD, EUR, GBP, CHF, and JPY.

It was the first bitcoin exchange to display its market data on the [Bloomberg Terminal](https://www.investopedia.com/terms/b/bloomberg_terminal.asp), the first to pass a cryptographically verifiable proof-of-reserves audit, and one of the first exchanges to offer leveraged bitcoin margin trading.

## Using the connector

Because [Kraken](https://www.kraken.com/) is a centralized exchange, you will need to generate and provide your API keys to trade using Hummingbot.

```
Enter your Kraken API key >>>
Enter your Kraken secret key >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip
    For copying and pasting into Hummingbot, see [this page](https://hummingbot.zendesk.com/hc/en-us/articles/900004871203-Copy-and-paste-your-API-keys) for more instructions in our Support guide.

### Creating Kraken API keys

The article below in their documentation shows step-by-step instructions on how to create API keys in the Kraken exchange.

- [How to create an API](https://support.kraken.com/hc/en-us/articles/360000919966-How-to-generate-an-API-key-pair-)

Take note that for your API keys to work with Hummingbot, **set the Nonce Window to at least 10**.

![kraken](/assets/img/kraken_nonce_window.png)

!!! warning
    For API key permissions, we recommend using only #Orders & Trades# enabled API keys; enabling #withdraw, transfer, or the equivalent# is unnecessary for current Hummingbot strategies.

Shows nonce reminder when adding API keys to Kraken.

![kraken](/assets/img/kraken_nonce.png)

Also, note that your account must have funds to avoid getting this error when connecting your Kraken API on Hummingbot.

```
Failed connections:                                                                                      |
    kraken: {'error': {'error': []}}

10:12:24 - kraken_market - Error received from https://api.kraken.com/0/private/Balance. Response is {'error': []}.
```

### Asset codes

Kraken uses asset codes in front of some pairs as a classification system. Asset codes starting with **'X'** represent cryptocurrencies, though this is no longer followed for the newest coins. Asset codes starting with **'Z'** represent fiat currencies.

BTC is represented as XBT in this exchange. Therefore trading on this pair is viewed as XXBT, e.g., XXBT-USDT. However, Hummingbot uses symbol conversion so that it will be entered as `BTC-USDT`. For e.g.
![kraken](/assets/img/kraken_sample.png)

This article shows the complete list of assets and their corresponding asset codes.

- [How to interpret asset codes](https://support.kraken.com/hc/en-us/articles/360001185506-How-to-interpret-asset-codes)

## Miscellaneous info

### Minimum order sizes

Kraken's minimum order volume is denominated in **base currency**. Refer to their article below for the minimum order size per market.

- [Minimum order size for trading](https://support.kraken.com/hc/en-us/articles/205893708-Minimum-order-size-volume-for-trading)

### Transaction fees

Kraken charges 0.16% on maker fees and 0.26% on taker orders for almost all of their cryptocurrency pairs. At the same time, they charge 0.20% on both maker and taker orders if trading on fiat and stablecoin base currency pairs.

Users who trade high volumes can receive more discounts on trading fees. Read through below for more information.

- [Kraken Fee Schedule](https://www.kraken.com/features/fee-schedule)

Hummingbot users can override the default fees by editing [`conf_fee_overrides.yml`](/operation/override-fees/).
