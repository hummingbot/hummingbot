# AscendEX

AscendEX, formerly BitMax, is a leading digital asset financial platform with a comprehensive product suite including altcoin trading for spot, margin, and futures, wallet services for over 100 cryptocurrencies, and innovative staking support for top blockchain projects.

AscendEX is a Singapore-based crypto exchange launched in July 2018.

## Using the connector

To use [AscendEX](https://ascendex.com/en/global-digital-asset-platform) connector, you will need to generate and provide your API key to trade using Hummingbot.

```
Enter your AscendEx API key >>>
Enter your AscendEx secret API key >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip
    For copying and pasting into Hummingbot, see [this page](https://hummingbot.zendesk.com/hc/en-us/articles/900004871203-Copy-and-paste-your-API-keys) for more instructions in our Hummingbot Help Center

### Creating AscendEX API keys

1. Log in to your account at [here](https://ascendex.com/en/login), then click your profile > API settings (If you do not have an account, you will have to create one and verify your ID.)

!!! tip
    You must enable 2FA in your AscendEX account to create the API key. [How to enable 2FA](https://ascendex.com/en/help-center/articles/360053013514)?

![](/assets/img/account-ascend-ex.png)

2. Then click the new API key.

![](/assets/img/api-ascend-ex.png)

!!! warning
    For API key permissions, we recommend using `trade` and `view` enabled API keys; enabling `transfer,` `or the equivalent is unnecessary `for current Hummingbot strategies.

3. Now that you have created an API key, connect it to Hummingbot by using the `connect` command.

Make sure you store your Secret Key somewhere secure and do not share it with anyone. Your Secret Key will only be displayed once at the time when you create the API.

!!! warning
    If you lose your Secret Key, you can delete the API and create a new one. However, it will be impossible to reuse the same API.

## Miscellaneous info

### Maximum and minimum order sizes

See [this page](https://ascendex.com/en/help-center/articles/360025991074) for the maximum and minimum order size for all trading pairs.
The maximum order size is 200,000 USDT, while the minimum order size is 5 USDT.

### Transaction fees

AscendEX employs a tiered VIP transaction fee & rebate structure for both traders and BTMX holders within the AscendEX ecosystem.
VIP tiers have discounts set against base trading fees and are based off (i) trailing 30-day trade volume across both asset classes (in USDT) OR (ii) trailing 30-day average unlock BTMX holdings.

By default, trading fees for this exchange charge a fee of 0.1% for makers and 0.1% for takers on large market cap assets and 0.2% for maker fee, and 0.2% for taker fee on altcoins.

- [Transaction Fees](https://ascendex.com/en/feerate/transactionfee-traderate)

Users can override the default fees by editing [`conf_fee_overrides.yml`](/operation/override-fees/).
