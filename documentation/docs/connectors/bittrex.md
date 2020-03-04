# Bittrex Connector

## About Bittrex Global

Bittrex is a global, centralized cryptocurrency exchange based in Seattle, USA.  It was founded in 2013 and began its operations in 2014. It is an intuitive and easy to navigate exchange platform often finding its way into the top 3 US exchanges in terms of trading volume.


## Using the Connector

[Bittrex](https://international.bittrex.com/) is a centralized exchange and an API key is required in order to trade using Hummingbot.

```
Enter your Bittrex API key >>>
Enter your Bittrex secret key >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip "Copying and pasting into Hummingbot"
    See [this page](/faq/troubleshooting/#paste-items-from-clipboard-in-putty) for more instructions in our Support section.


### Creating Bittrex API Keys

1 - Log in to https://international.bittrex.com/ or create an account in [this page](https://international.bittrex.com/account/register).

!!! note
    Ensure first that 2FA is enabled to proceed with the next steps. Refer to [this page](https://bittrex.zendesk.com/hc/en-us/articles/115000198612-Two-Factor-Authentication-2FA-) for more information.

2 - Click **Account** then select **API Keys** under the site settings section.

![bittrex-api-key](/assets/img/bittrex_api_key.png)

3 - Add a new key, enable **Read Info** and **Trade** then save to enter 2FA code.

!!! warning "API key permissions"
    We recommend using only **"trade"** enabled API keys; enabling **"withdraw", "transfer", or the equivalent** is unnecessary for current Hummingbot strategies.

4 - The secret key will only be shown once. Make sure to save and keep this information somewhere safe as it can be used to recover a lost 2FA. In case of a lost security key, delete the API and create a new one. However, it will be impossible to reuse the same API.


## Miscellaneous Info

### Minimum Order Sizes

Minimum order size varies per market. All minimum trade quantities can be found in the following public API:

```
https://bittrex.com/api/v1.1/public/getmarkets
```

`MinTradeSize` denotes the minimum order size for each market. For example, trading pair ETH-ZRX minimum order size is 5.81577937 ZRX.

```
"MarketCurrency": "ZRX",
"BaseCurrency": "ETH",
"MarketCurrencyLong": "0x Protocol",
"BaseCurrencyLong": "Ethereum",
"MinTradeSize": 5.81577937,
"MarketName": "ETH-ZRX",
"IsActive": true,
"IsRestricted": false,
"Created": "2018-02-15T23:33:55.923",
"Notice": null,
"IsSponsored": null,
"LogoUrl": "https://bittrexblobstorage.blob.core.windows.net/public/60b380a9-5161-4afe-a8f8-dbf3a8210033.png"
```

### Transaction Fees

Bittrex charges 0.25% in both maker and taker fees for most users. However, those who trade in high volumes can trade at discounted rates. Refer to [Fee Schedule](https://bittrex.zendesk.com/hc/en-us/articles/115000199651-What-fees-does-Bittrex-charge-/) section for more details.

Users can override the default fees by editing [`conf_fee_overrides.yml`](https://docs.hummingbot.io/advanced/fee-overrides/).
